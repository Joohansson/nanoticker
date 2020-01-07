"""Read data from multiple public nano node monitors and combines stats in json"""
"""Author: Joohansson (Json)"""

import json
import simplejson
import time
import datetime
import asyncio
import aiohttp
import async_timeout
import ssl
import sys
import requests
import re
import logging

#Own references
import repList

"""CUSTOM VARS"""
BETA = False #SET TO False FOR MAIN NET

if BETA:
    #nodeUrl = 'http://[::1]:7076' #main
    nodeUrl = 'http://[::1]:55000' #beta
    logFile="repstat.log"
    statFile = '/var/www/monitor/stats-beta.json' #placed in a web server for public access
    monitorFile = '/var/www/monitor/monitors-beta.json' #placed in a web server for public access
    activeCurrency = 'nano-beta' #nano, banano or nano-beta
    ninjaMonitors = 'https://beta.mynano.ninja/api/accounts/monitors' #beta

else:
    nodeUrl = 'http://[::1]:7076' #main
    logFile="/root/py/nano/repstat.log"
    statFile = '/var/www/repstat/public_html/json/stats.json' #placed in a web server for public access
    monitorFile = '/var/www/repstat/public_html/json/monitors.json' #placed in a web server for public access
    activeCurrency = 'nano' #nano, banano or nano-beta
    ninjaMonitors = 'https://mynano.ninja/api/accounts/monitors' #beta

# For pushing stats to the blockchain
source_account = 'nano_1ticker1j6fax9ke4jajppaj6gcuhfys9sph3hhprq3ewj31z4qndbcb5feq'
#source_account = 'nano_3oiqirkpqje1yohdrm8hq4pu1yp7hwwddjgdbftcau63rjyppi15q6858asy'
rep_account = 'nano_1iuz18n4g4wfp9gf7p1s8qkygxw7wx9qfjq6a9aq68uyrdnningdcjontgar'
priv_key = '31d30eda437f3a243212fd2aebfa0f855a230a1aa237344f0eb7d233c35974ea'
#priv_key = '4FD52C089CE842CF60C0F97E053B066B3BC8C1650DC618E11C77D72ED2FB0992'
cph_account = 'nano_1cph1t1yp3nb9wq3zkh6q69yxq5ikwz4rt3jiy9kqxdmbyjz48shrmt9neyn'
peers_account = 'nano_1peers1jrgie5gji5oasgi5zawc1bjb9r138e88g4ia9to56dih7sp5p19xy'
difficulty_account = 'nano_1diff1tojcgttgewe1pkm4yyjwbbb51oewbro3wtsnxjrtz5i9iuuq3f4frt'
#cph_account = 'nano_3oiqirkpqje1yohdrm8hq4pu1yp7hwwddjgdbftcau63rjyppi15q6858asy'
#peers_account = 'nano_3oiqirkpqje1yohdrm8hq4pu1yp7hwwddjgdbftcau63rjyppi15q6858asy'
#difficulty_account = 'nano_3oiqirkpqje1yohdrm8hq4pu1yp7hwwddjgdbftcau63rjyppi15q6858asy'

"""LESS CUSTOM VARS"""
minCount = 1 #initial required block count
timeout = 10 #http request timeout for API
runAPIEvery = 15 #run API check every X sec
runPeersEvery = 120 #run peer check every X sec
runStatEvery = 3600 #publish stats to blockchain every x sec
maxURLRequests = 250 #maximum concurrent requests

"""CONSTANTS"""
pLatestVersionStat = 0 #percentage running latest protocol version
pTypesStat = 0 #percentage running tcp
pStakeTotalStat = 0 #percentage connected online weight of maximum
pStakeRequiredStat = 0 #percentage of connected online weight of maxium required for voting
pStakeLatestVersionStat = 0 #percentage of connected online weight that is on latest version
peerInfo = [] #connected peers with weight info
confCountLimit = 500 #lower limit for block count to include confirmation average
confSpanLimit = 30000 #lower limit for time span to include confirmation average

if BETA:
    repsInit = repList.repsInitB
    blacklist = repList.blacklistB
else:
    repsInit = repList.repsInitM
    blacklist = repList.blacklistM

"""VARIABLES"""
reps = repsInit
latestOnlineWeight = 0 #used for calculating PR status
latestRunStatTime = 0 #fine tuning loop time for stats
latestGlobalBlocks = []
latestGlobalPeers = []
latestGlobalDifficulty = []

logging.basicConfig(level=logging.INFO,filename=logFile, filemode='a', format='%(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

#Calculate the average value of the 50% middle percentile from a list
def median(lst):
    if lst == None or lst == []:
        return 0
    if len(lst) == 1:
        return lst[0]

    sortedLst = sorted(lst)
    lstLen = len(lst)
    index = (lstLen - 1) // 2

    # Do average of mid sub list
    if lstLen > 6:
        if (lstLen % 2):
            startIndex = index - (lstLen // 4)

        else:
            startIndex = index - (lstLen // 4) + 1

        endIndex = index + (lstLen // 4) + 1
        range = sortedLst[startIndex:endIndex]
        return sum(range) / len(range) #average of the sub list

    # Do normal median
    else:
        if (lstLen % 2):
            return sortedLst[index]
        else:
            return (sortedLst[index] + sortedLst[index + 1])/2.0

"""
def median(lst):
    sortedLst = sorted(lst)
    lstLen = len(lst)
    index = (lstLen - 1) // 2

    if (lstLen % 2):
        return sortedLst[index]
    else:
        return (sortedLst[index] + sortedLst[index + 1])/2.0
"""

async def fetch(session, url):
    async with session.get(url) as response:
        try:
            if (response.status == 200):
                r = await response.text()
                return r
        except:
            pass

async def getMonitor(url):
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            r = await fetch(session, url)
            try:
                rjson = json.loads(r)
                if int(rjson['currentBlock']) > 0:
                    return [rjson, True, url, r]
            except:
                return [{}, False, url, r]
    except:
        pass

async def verifyMonitor(url):
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            r = await fetch(session, url)
            try:
                rjson = json.loads(r)
                if int(rjson['currentBlock']) > 0:
                    url = url.replace('/api.php','')
                    return [rjson['nanoNodeAccount'], url]
            except:
                pass
    except:
        pass

SSL_PROTOCOLS = (asyncio.sslproto.SSLProtocol,)
try:
    import uvloop.loop
except ImportError:
    pass
else:
    SSL_PROTOCOLS = (*SSL_PROTOCOLS, uvloop.loop.SSLProtocol)

def ignore_aiohttp_ssl_error(loop):
    """Ignore aiohttp #3535 / cpython #13548 issue with SSL data after close

    There is an issue in Python 3.7 up to 3.7.3 that over-reports a
    ssl.SSLError fatal error (ssl.SSLError: [SSL: KRB5_S_INIT] application data
    after close notify (_ssl.c:2609)) after we are already done with the
    connection. See GitHub issues aio-libs/aiohttp#3535 and
    python/cpython#13548.

    Given a loop, this sets up an exception handler that ignores this specific
    exception, but passes everything else on to the previous exception handler
    this one replaces.

    Checks for fixed Python versions, disabling itself when running on 3.7.4+
    or 3.8.

    """
    if sys.version_info >= (3, 7, 4):
        return

    orig_handler = loop.get_exception_handler()
    def ignore_ssl_error(loop, context):
        if context.get("message") in {
            "SSL error in data received",
            "Fatal error on transport",
        }:
            # validate we have the right exception, transport and protocol
            exception = context.get('exception')
            protocol = context.get('protocol')
            if (
                isinstance(exception, ssl.SSLError)
                and exception.reason == 'KRB5_S_INIT'
                and isinstance(protocol, SSL_PROTOCOLS)
            ):
                if loop.get_debug():
                    asyncio.log.logger.debug('Ignoring asyncio SSL KRB5_S_INIT error')
                return
        if orig_handler is not None:
            orig_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(ignore_ssl_error)

def chunks(l, n):
    """Yield successive n-sized chunks from l"""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def timeLog(msg):
    return str(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')) + ": " + msg

async def apiSleep(startTime):
    sleep = runAPIEvery - (time.time() - startTime)
    await asyncio.sleep(sleep)

async def peerSleep(startTime):
    sleep = runPeersEvery - (time.time() - startTime)
    await asyncio.sleep(sleep)

async def statSleep(startTime):
    global latestRunStatTime

    sleep = runStatEvery - (time.time() - startTime) - (time.time() - round(latestRunStatTime/10)*10 - runStatEvery)
    latestRunStatTime = time.time()
    await asyncio.sleep(sleep)

async def getAPI():
    global minCount
    global pLatestVersionStat
    global pTypesStat
    global pStakeTotalStat
    global pStakeRequiredStat
    global pStakeLatestVersionStat
    global peerInfo
    global activeCurrency
    global latestGlobalBlocks
    global latestGlobalPeers
    global latestGlobalDifficulty

    await asyncio.sleep(18) #Wait for some values to be calculated from getPeers
    while 1:
        #log.info(timeLog("Get API"))
        jsonData = []
        startTime = time.time() #to measure the loop speed
        """Split URLS in max X concurrent requests"""
        for chunk in chunks(reps, maxURLRequests):
            tasks = []
            for path in chunk:
                if len(path) > 6:
                    tasks.append(asyncio.ensure_future(getMonitor('%s/api.php' %path)))

            try:
                with async_timeout.timeout(timeout):
                    await asyncio.gather(*tasks)

            except asyncio.TimeoutError as t:
                pass
                #log.warning(timeLog('Monitor API read timeout: %r' %t))

            for i, task in enumerate(tasks):
                try:
                    if task.result() is not None and task.result():
                        if (task.result()[1]):
                            jsonData.append(task.result()[0])
                            #log.info(timeLog('Valid: ' + task.result()[0]['nanoNodeName']))
                        else:
                            log.warning(timeLog('Could not read json from %s. Result: %s' %(task.result()[2], task.result()[3])))

                except Exception as e:
                    #for example when tasks timeout
                    pass
                    #log.warning(timeLog('Could not read response. Error: %r' %e))


        countData = []
        cementedData = []
        uncheckedData = []
        peersData = []
        syncData = []
        conf50Data = []
        conf75Data = []
        conf90Data = []
        conf99Data = []
        confAveData = []
        memoryData = []
        procTimeData = []
        multiplierData = []

        #PR ONLY
        countData_pr = []
        cementedData_pr = []
        uncheckedData_pr = []
        peersData_pr = []
        syncData_pr = []
        conf50Data_pr = []
        conf75Data_pr = []
        conf90Data_pr = []
        conf99Data_pr = []
        confAveData_pr = []
        memoryData_pr = []
        procTimeData_pr = []
        multiplierData_pr = []

        #Convert all API json inputs
        fail = False #If a REP does not support one or more of the entries
        supportedReps = [] #reps supporting all parameters

        try:
            if jsonData is None or type(jsonData[0]) == bool:
                #log.info(timeLog('type error'))
                await apiSleep(startTime)
                continue
        except:
            await apiSleep(startTime)
            continue

        for j in jsonData:
            if len(j) > 0:
                try:
                    count = int(j['currentBlock'])

                    #skip if the node is out of sync
                    if count < minCount:
                        #log.info(timeLog('mincount warning'))
                        continue
                except Exception as e:
                    #log.warning(timeLog('currentBlock warning'))
                    count = 0
                    continue

                try:
                    name = j['nanoNodeName']
                except Exception as e:
                    name = -1
                    fail = True

                #Validate if the monitor is for nano, banano or nano-beta (if possible)
                try:
                    currency = j['currency']
                    if currency != activeCurrency:
                        log.info(timeLog('Bad currency setting: ' + name))
                        continue
                except Exception as e:
                    pass

                try:
                    nanoNodeAccount = j['nanoNodeAccount']
                except Exception as e:
                    nanoNodeAccount = -1
                    fail = True

                try:
                    protocolVersion = j['protocol_version']
                except Exception as e:
                    protocolVersion = -1
                    pass

                try:
                    version = j['version']
                except Exception as e:
                    version = -1
                    pass

                try:
                    weight = int(j['votingWeight'])
                    if (weight >= latestOnlineWeight*0.001):
                        PRStatus = True
                    else:
                        PRStatus = False
                except Exception as e:
                    weight = -1
                    PRStatus = False
                    pass

                try:
                    cemented = int(j['cementedBlocks'])
                except Exception as e:
                    cemented = -1
                    fail = True
                try:
                    unchecked = int(j['uncheckedBlocks'])
                except Exception as e:
                    unchecked = -1
                    fail = True
                try:
                    peers = int(j['numPeers'])
                except Exception as e:
                    peers = -1
                    fail = True
                try:
                    sync = float(j['blockSync'])
                except Exception as e:
                    sync = -1
                    fail = True
                try:
                    conf50 = int(j['confirmationInfo']['percentile50'])
                except Exception as e:
                    conf50 = -1
                    fail = True
                try:
                    conf75 = int(j['confirmationInfo']['percentile75'])
                except Exception as e:
                    conf75 = -1
                    fail = True
                try:
                    conf90 = int(j['confirmationInfo']['percentile90'])
                except Exception as e:
                    conf90 = -1
                    fail = True
                try:
                    conf99 = int(j['confirmationInfo']['percentile99'])
                except Exception as e:
                    conf99 = -1
                    fail = True
                try:
                    confAve = int(j['confirmationInfo']['average'])
                except Exception as e:
                    confAve = -1
                    fail = True
                try:
                    confCount = int(j['confirmationInfo']['count'])
                except Exception as e:
                    confCount = -1
                try:
                    confSpan = int(j['confirmationInfo']['timeSpan'])
                except Exception as e:
                    confSpan = -1
                try:
                    memory = int(j['usedMem'])
                except Exception as e:
                    memory = -1
                    fail = True
                try:
                    procTime = int(j['apiProcTime'])
                except Exception as e:
                    procTime = -1
                    fail = True
                try:
                    multiplier = float(j['active_difficulty']['multiplier'])
                except Exception as e:
                    multiplier = -1
                    fail = True

                #read all monitor info
                countData.append(count)
                if (PRStatus):
                    countData_pr.append(count)

                if (cemented > 0):
                    cementedData.append(cemented)
                    if (PRStatus):
                        cementedData_pr.append(cemented)

                if (unchecked > 0):
                    uncheckedData.append(unchecked)
                    if (PRStatus):
                        uncheckedData_pr.append(unchecked)

                if (peers > 0):
                    peersData.append(peers)
                    if (PRStatus):
                        peersData_pr.append(peers)

                if (sync > 0):
                    syncData.append(sync)
                    if (PRStatus):
                        syncData_pr.append(sync)

                if (conf50 >= 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf50Data.append(conf50)
                    if (PRStatus):
                        conf50Data_pr.append(conf50)

                if (conf75 >= 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf75Data.append(conf75)
                    if (PRStatus):
                        conf75Data_pr.append(conf75)

                if (conf90 >= 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf90Data.append(conf90)
                    if (PRStatus):
                        conf90Data_pr.append(conf90)

                if (conf99 >= 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf99Data.append(conf99)
                    if (PRStatus):
                        conf99Data_pr.append(conf99)

                if (confAve >= 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    confAveData.append(confAve)
                    if (PRStatus):
                        confAveData_pr.append(confAve)

                if (memory > 0):
                    memoryData.append(memory)
                    if (PRStatus):
                        memoryData_pr.append(memory)

                if (procTime > 0):
                    procTimeData.append(procTime)
                    if (PRStatus):
                        procTimeData_pr.append(procTime)

                if (multiplier > 0):
                    multiplierData.append(multiplier)
                    if (PRStatus):
                        multiplierData_pr.append(multiplier)

                #If weight missing, try find matching weight from peer table
                try:
                    if weight < 0:
                        for p in peerInfo:
                            if str(nanoNodeAccount) == str(p['account']):
                                weight = str(int(p['weight']) / int(1000000000000000000000000000000))
                except:
                    pass

                supportedReps.append({'name':name, 'nanoNodeAccount':nanoNodeAccount,
                'version':version, 'protocolVersion':protocolVersion, 'currentBlock':count, 'cementedBlocks':cemented,
                'unchecked':unchecked, 'numPeers':peers, 'confAve':confAve, 'confMedian':conf50, 'weight':weight,
                'memory':memory, 'procTime':procTime, 'multiplier':multiplier, 'supported':not fail, 'PR':PRStatus})
                fail = False

            else:
                log.warning(timeLog("Empty json from API calls"))

        blockCountMedian = 0
        cementedMedian = 0
        uncheckedMedian = 0
        peersMedian = 0
        diffMedian = 0
        conf50Median = 0
        conf75Median = 0
        conf90Median = 0
        conf99Median = 0
        confAveMedian = 0
        memoryMedian = 0
        procTimeMedian = 0
        multiplierMedian = 0

        blockCountMax = 0
        cementedMax = 0
        uncheckedMax = 0
        peersMax = 0
        diffMax = 0
        memoryMax = 0
        procTimeMax = 0
        multiplierMax = 0

        blockCountMin = 0
        cementedMin = 0
        uncheckedMin = 0
        peersMin = 0
        confAveMin = 0
        memoryMin = 0
        procTimeMin = 0
        multiplierMin = 0

        #PR ONLY
        blockCountMedian_pr = 0
        cementedMedian_pr = 0
        uncheckedMedian_pr = 0
        peersMedian_pr = 0
        diffMedian_pr = 0
        conf50Median_pr = 0
        conf75Median_pr = 0
        conf90Median_pr = 0
        conf99Median_pr = 0
        confAveMedian_pr = 0
        memoryMedian_pr = 0
        procTimeMedian_pr = 0
        multiplierMedian_pr = 0

        blockCountMax_pr = 0
        cementedMax_pr = 0
        uncheckedMax_pr = 0
        peersMax_pr = 0
        diffMax_pr = 0
        memoryMax_pr = 0
        procTimeMax_pr = 0
        multiplierMax_pr = 0

        blockCountMin_pr = 0
        cementedMin_pr = 0
        uncheckedMin_pr = 0
        peersMin_pr = 0
        confAveMin_pr = 0
        memoryMin_pr = 0
        procTimeMin_pr = 0
        multiplierMin_pr = 0

        try:
            if len(countData) > 0:
                blockCountMedian = int(median(countData))
                blockCountMax = int(max(countData))
                blockCountMin = int(min(countData))
                #Update the min allowed block count
                minCount = int(blockCountMax/2)

                #Calculate diff
                if (blockCountMax > 0):
                    diffMedian = blockCountMax - blockCountMedian
                    diffMax = blockCountMax - blockCountMin

            if len(cementedData) > 0:
                cementedMedian = int(median(cementedData))
                cementedMax = int(max(cementedData))
                cementedMin = int(min(cementedData))
            if len(uncheckedData) > 0:
                uncheckedMedian = int(median(uncheckedData))
                uncheckedMax = int(max(uncheckedData))
                uncheckedMin = int(min(uncheckedData))
            if len(peersData) > 0:
                peersMedian = int(median(peersData))
                peersMax = int(max(peersData))
                peersMin = int(min(peersData))
            if len(conf50Data) > 0:
                conf50Median = int(median(conf50Data))
            if len(conf75Data) > 0:
                conf75Median = int(median(conf75Data))
            if len(conf90Data) > 0:
                conf90Median = int(median(conf90Data))
            if len(conf99Data) > 0:
                conf99Median = int(median(conf99Data))
            if len(confAveData) > 0:
                confAveMedian = int(median(confAveData))
                confAveMin = int(min(confAveData))
            if len(memoryData) > 0:
                memoryMedian = int(median(memoryData))
                memoryMax = int(max(memoryData))
                memoryMin = int(min(memoryData))
            if len(procTimeData) > 0:
                procTimeMedian = int(median(procTimeData))
                procTimeMax = int(max(procTimeData))
                procTimeMin = int(min(procTimeData))
            if len(multiplierData) > 0:
                multiplierMedian = float(median(multiplierData))
                multiplierMax = float(max(multiplierData))
                multiplierMin = float(min(multiplierData))

            #PR ONLY
            if len(countData_pr) > 0:
                blockCountMedian_pr = int(median(countData_pr))
                blockCountMax_pr = int(max(countData_pr))
                blockCountMin_pr = int(min(countData_pr))

                #Calculate diff
                if (blockCountMax_pr > 0):
                    diffMedian_pr = blockCountMax_pr - blockCountMedian_pr
                    diffMax_pr = blockCountMax_pr - blockCountMin_pr

            if len(cementedData_pr) > 0:
                cementedMedian_pr = int(median(cementedData_pr))
                cementedMax_pr = int(max(cementedData_pr))
                cementedMin_pr = int(min(cementedData_pr))
            if len(uncheckedData_pr) > 0:
                uncheckedMedian_pr = int(median(uncheckedData_pr))
                uncheckedMax_pr = int(max(uncheckedData_pr))
                uncheckedMin_pr = int(min(uncheckedData_pr))
            if len(peersData_pr) > 0:
                peersMedian_pr = int(median(peersData_pr))
                peersMax_pr = int(max(peersData_pr))
                peersMin_pr = int(min(peersData_pr))
            if len(conf50Data_pr) > 0:
                conf50Median_pr = int(median(conf50Data_pr))
            if len(conf75Data_pr) > 0:
                conf75Median_pr = int(median(conf75Data_pr))
            if len(conf90Data_pr) > 0:
                conf90Median_pr = int(median(conf90Data_pr))
            if len(conf99Data_pr) > 0:
                conf99Median_pr = int(median(conf99Data_pr))
            if len(confAveData_pr) > 0:
                confAveMedian_pr = int(median(confAveData_pr))
                confAveMin_pr = int(min(confAveData_pr))
            if len(memoryData_pr) > 0:
                memoryMedian_pr = int(median(memoryData_pr))
                memoryMax_pr = int(max(memoryData_pr))
                memoryMin_pr = int(min(memoryData_pr))
            if len(procTimeData_pr) > 0:
                procTimeMedian_pr = int(median(procTimeData_pr))
                procTimeMax_pr = int(max(procTimeData_pr))
                procTimeMin_pr = int(min(procTimeData_pr))
            if len(multiplierData_pr) > 0:
                multiplierMedian_pr = float(median(multiplierData_pr))
                multiplierMax_pr = float(max(multiplierData_pr))
                multiplierMin_pr = float(min(multiplierData_pr))

            #Write output file
            statData = {\
                "blockCountMedian":int(blockCountMedian),\
                "blockCountMax":int(blockCountMax),\
                "blockCountMin":int(blockCountMin),\
                "cementedMedian":int(cementedMedian),\
                "cementedMax":int(cementedMax),\
                "cementedMin":int(cementedMin),\
                "uncheckedMedian":int(uncheckedMedian),\
                "uncheckedMax":int(uncheckedMax),\
                "uncheckedMin":int(uncheckedMin),\
                "peersMedian":int(peersMedian),\
                "peersMax":int(peersMax),\
                "peersMin":int(peersMin),\
                "diffMedian":float(diffMedian),\
                "diffMax":float(diffMax),\
                "memoryMedian":int(memoryMedian),\
                "memoryMax":int(memoryMax),\
                "memoryMin":int(memoryMin),\
                "procTimeMedian":int(procTimeMedian),\
                "procTimeMax":int(procTimeMax),\
                "procTimeMin":int(procTimeMin),\
                "multiplierMedian":float(multiplierMedian),\
                "multiplierMax":float(multiplierMax),\
                "multiplierMin":float(multiplierMin),\
                "conf50Median":int(conf50Median),\
                "conf75Median":int(conf75Median),\
                "conf90Median":int(conf90Median),\
                "conf99Median":int(conf99Median),\
                "confAveMedian":int(confAveMedian),\
                "confAveMin":int(confAveMin),\
                "lenBlockCount":int(len(countData)),\
                "lenCemented":int(len(cementedData)),\
                "lenUnchecked":int(len(uncheckedData)),\
                "lenPeers":int(len(peersData)),\
                "lenConf50":int(len(conf50Data)),\
                "lenMemory":int(len(memoryData)),\
                "lenProcTime":int(len(procTimeData)),\
                "lenMultiplier":int(len(multiplierData)),\
                #PR ONLY START
                "blockCountMedian_pr":int(blockCountMedian_pr),\
                "blockCountMax_pr":int(blockCountMax_pr),\
                "blockCountMin_pr":int(blockCountMin_pr),\
                "cementedMedian_pr":int(cementedMedian_pr),\
                "cementedMax_pr":int(cementedMax_pr),\
                "cementedMin_pr":int(cementedMin_pr),\
                "uncheckedMedian_pr":int(uncheckedMedian_pr),\
                "uncheckedMax_pr":int(uncheckedMax_pr),\
                "uncheckedMin_pr":int(uncheckedMin_pr),\
                "peersMedian_pr":int(peersMedian_pr),\
                "peersMax_pr":int(peersMax_pr),\
                "peersMin_pr":int(peersMin_pr),\
                "diffMedian_pr":float(diffMedian_pr),\
                "diffMax_pr":float(diffMax_pr),\
                "memoryMedian_pr":int(memoryMedian_pr),\
                "memoryMax_pr":int(memoryMax_pr),\
                "memoryMin_pr":int(memoryMin_pr),\
                "procTimeMedian_pr":int(procTimeMedian_pr),\
                "procTimeMax_pr":int(procTimeMax_pr),\
                "procTimeMin_pr":int(procTimeMin_pr),\
                "multiplierMedian_pr":float(multiplierMedian_pr),\
                "multiplierMax_pr":float(multiplierMax_pr),\
                "multiplierMin_pr":float(multiplierMin_pr),\
                "conf50Median_pr":int(conf50Median_pr),\
                "conf75Median_pr":int(conf75Median_pr),\
                "conf90Median_pr":int(conf90Median_pr),\
                "conf99Median_pr":int(conf99Median_pr),\
                "confAveMedian_pr":int(confAveMedian_pr),\
                "confAveMin_pr":int(confAveMin_pr),\
                "lenBlockCount_pr":int(len(countData_pr)),\
                "lenCemented_pr":int(len(cementedData_pr)),\
                "lenUnchecked_pr":int(len(uncheckedData_pr)),\
                "lenPeers_pr":int(len(peersData_pr)),\
                "lenConf50_pr":int(len(conf50Data_pr)),\
                "lenMemory_pr":int(len(memoryData_pr)),\
                "lenProcTime_pr":int(len(procTimeData_pr)),\
                "lenMultiplier_pr":int(len(multiplierData_pr)),\
                #PR ONLY END
                "pLatestVersionStat":pLatestVersionStat,\
                "pTypesStat":pTypesStat,\
                "pStakeTotalStat":pStakeTotalStat,\
                "pStakeRequiredStat":pStakeRequiredStat,\
                "pStakeLatestVersionStat":pStakeLatestVersionStat,\
                "pStakeOnline":latestOnlineWeight,\
                "lastUpdated":str(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),\
                "lastUpdatedUnix":str(time.time()),\
                }

            #save to global vars used for pushing to blockchain later
            latestGlobalBlocks.append({"time":time.time(), "data": statData['cementedMedian_pr']})
            latestGlobalPeers.append({"time":time.time(), "data": statData['peersMedian_pr']})
            latestGlobalDifficulty.append({"time":time.time(), "data": statData['multiplierMedian_pr']})

        except:
            pass

        if blockCountMedian > 0 and blockCountMax > 0:
            try:
                with open(statFile, 'w') as outfile:
                    outfile.write(simplejson.dumps(statData, indent=2))
            except Exception as e:
                log.error(timeLog('Could not write stat data. Error: %r' %e))

            try:
                with open(monitorFile, 'w') as outfile:
                    outfile.write(simplejson.dumps(supportedReps, indent=2))
            except Exception as e:
                log.error(timeLog('Could not write monitor data. Error: %r' %e))

        #print(time.time() - startTime)
        #calculate final sleep based on execution time
        await apiSleep(startTime)

async def getPeers():
    global reps
    global pLatestVersionStat
    global pTypesStat
    global pStakeTotalStat
    global pStakeRequiredStat
    global pStakeLatestVersionStat
    global peerInfo
    global latestOnlineWeight

    while 1:
        startTime = time.time() #to measure the loop speed
        pPeers = []
        pVersions = []
        pStakeTot = 0
        pStakeReq = 0
        pStakeLatest = 0
        supply = 133248061996216572282917317807824970865

        #log.info(timeLog("Verifying peers"))
        monitorPaths = repsInit.copy()

        #Grab connected peer IPs from the node
        params = {
            "action": "peers",
            "peer_details": True,
        }

        try:
            resp = requests.post(url=nodeUrl, json=params, timeout=10)
            peers = resp.json()['peers']
            for ipv6,value in peers.items():
                if '[::ffff:' in ipv6: #ipv4
                    ip = re.search('ffff:(.*)\]:', ipv6).group(1)
                else: #ipv6
                    ip = '[' + re.search('\[(.*)\]:', ipv6).group(1) +']'

                if ip is not "":
                    #Only try to find more monitors from peer IP in main network
                    if not BETA:
                        #Combine with previous list and ignore duplicates
                        exists = False
                        for url in monitorPaths:
                            if 'http://'+ip == url:
                                exists = True
                                break
                        if not exists:
                            monitorPaths.append('http://'+ip)

                        exists = False
                        for url in monitorPaths:
                            if 'http://'+ip+'/nano' == url:
                                exists = True
                                break
                        if not exists:
                            monitorPaths.append('http://'+ip+'/nano')

                        exists = False
                        for url in monitorPaths:
                            if 'http://'+ip+'/nanoNodeMonitor' == url:
                                exists = True
                                break
                        if not exists:
                            monitorPaths.append('http://'+ip+'/nanoNodeMonitor')

                        exists = False
                        for url in monitorPaths:
                            if 'http://'+ip+'/monitor' == url:
                                exists = True
                                break
                        if not exists:
                            monitorPaths.append('http://'+ip+'/monitor')

                    #Read protocol version and type
                    pVersions.append(value['protocol_version'])
                    pPeers.append({"ip":ipv6, "version":value["protocol_version"], "type":value["type"], "weight":0, "account": ""})

        except Exception as e:
            log.warning(timeLog("Could not read peers from node RPC. %r" %e))
            await peerSleep(startTime)
            continue #break out of main loop and try again next iteration

        #Grab voting weight stat
        params = {
            "action": "confirmation_quorum",
            "peer_details": True,
        }
        try:
            resp = requests.post(url=nodeUrl, json=params, timeout=10)
            pStakeTot = resp.json()['peers_stake_total']
            pStakeReq = resp.json()['peers_stake_required']
            latestOnlineWeight = int(resp.json()['online_stake_total']) / int(1000000000000000000000000000000) #used for calculating PR status

            #Find matching IP and include weight in original peer list
            for peer in resp.json()['peers']:
                for i,cPeer in enumerate(pPeers):
                    if peer['ip'] == cPeer['ip']:
                        pPeers[i] = dict(cPeer, **{"weight": peer['weight'], "account": peer['account']}) #update previous vaule
                        continue

        except Exception as e:
            log.warning(timeLog("Could not read quorum from node RPC. %r" %e))
            pass

        #Save as global list
        if len(pPeers) > 0:
            peerInfo = pPeers.copy()

        #Grab supply
        params = {
            "action": "available_supply"
        }
        try:
            resp = requests.post(url=nodeUrl, json=params, timeout=10)
            tempSupply = resp.json()['available']
            if int(tempSupply) > 0: #To ensure no devision by zero
                supply = tempSupply

        except Exception as e:
            log.warning(timeLog("Could not read supply from node RPC. %r" %e))
            pass

        #PERCENTAGE STATS
        maxVersion = 0
        versionCounter = 0
        if len(pVersions) > 0:
            maxVersion = int(max(pVersions))
            #Calculate percentage of nodes on latest version
            versionCounter = 0
            for version in pVersions:
                if int(version) == maxVersion:
                    versionCounter += 1

        #Require at least 5 monitors to be at latest version to use as base, or use second latest version
        if versionCounter < 5 and len(pVersions) > 0:
            #extract second largest number by first removing duplicates
            simplified = list(set(pVersions))
            simplified.sort()
            maxVersion = int(simplified[-2])
            versionCounter = 0
            for version in pVersions:
                if int(version) == maxVersion:
                    versionCounter += 1

        if len(pVersions) > 0:
            pLatestVersionStat = versionCounter / int(len(pVersions)) * 100
        else:
            pLatestVersionStat = 0

        pStakeTotalStat = int(pStakeTot) / int(supply) * 100
        pStakeRequiredStat = int(pStakeReq) / int(supply) * 100

        #Calculate portion of weight and TCP in the latest versions
        combinedWeightInLatest = 0
        TCPInLatestCounter = 0
        for peer in pPeers:
            if int(peer['version']) == int(maxVersion):
                combinedWeightInLatest = combinedWeightInLatest + int(peer['weight'])

            if (peer['type'] == 'tcp'):
                TCPInLatestCounter += 1

        pStakeLatestVersionStat = int(combinedWeightInLatest) / int(supply) * 100

        if len(pPeers) > 0:
            pTypesStat = TCPInLatestCounter / int(len(pPeers)) * 100
        else:
            pTypesStat = 0

        #Get monitors from Ninja API
        try:
            r = requests.get(ninjaMonitors, timeout=30)
            monitors = r.json()

            if r is not None:
                if len(r.json()) > 0:
                    for monitor in r.json():
                        try:
                            url = monitor['monitor']['url']
                            #Correct bad ending in some URLs like /api.php which will be added later
                            url = url.replace('/api.php','')
                            if url[-1] == '/': #ends with /
                                url = url[:-1]

                            #Ignore duplicates (IPs may still lead to same host name but that will be dealt with later)
                            exists = False
                            for path in monitorPaths:
                                if path == url:
                                    exists = True
                                    break
                            if not exists:
                                monitorPaths.append(url)
                        except:
                            log.warning(timeLog("Invalid Ninja monitor"))

        except Exception as e:
            log.warning(timeLog("Could not read monitors from ninja. %r" %e))

        #Apply blacklist
        for i,node in enumerate(monitorPaths):
            for exl in blacklist:
                if node == exl:
                    del monitorPaths[i]
                    break

        #Verify all URLS
        validPaths = []
        repAccounts = []
        """Split URLS in max X concurrent requests"""
        for chunk in chunks(monitorPaths, maxURLRequests):
            tasks = []
            for path in chunk:
                if len(path) > 6:
                    tasks.append(asyncio.ensure_future(verifyMonitor('%s/api.php' %path)))

            try:
                with async_timeout.timeout(timeout):
                    await asyncio.gather(*tasks)

            except asyncio.TimeoutError as t:
                pass
                #log.warning(timeLog('Monitor Peer read timeout: %r' %t))

            for i, task in enumerate(tasks):
                try:
                    if task.result() is not None and task.result():
                        #Save valid peer urls
                        #Check for duplicate account (IP same as hostname)
                        exists = False
                        for account in repAccounts:
                            if task.result()[0] == account:
                                exists = True
                                break
                        if not exists:
                            validPaths.append(task.result()[1])
                        repAccounts.append(task.result()[0])

                except Exception as e:
                    pass

        #Update the final list
        reps = validPaths.copy()
        #log.info(reps)

        await peerSleep(startTime)

async def publishStatBlock(source_account, priv_key, dest_account, rep_account, stringVal):
    # get info from sending account
    params = {
        'action': 'account_info',
        'account': source_account,
        'count': 1,
        'pending': 'true'
    }

    try:
        log.info(timeLog("Getting info"))
        resp = requests.post(url=nodeUrl, json=params, timeout=60)
        account_info = resp.json()

        # calculate the state block balance after the send
        adjustedbal = str(int(account_info['balance']) - stringVal)
        # get previous hash
        if 'frontier' in account_info:
            prev = account_info["frontier"]
        else:
            log.warning(timeLog("Source account not opened yet"))
            return False

    except Exception as e:
        log.warning(timeLog("Could not get block info. %r" %e))
        return False

    # create send block
    params = {
        'action': 'block_create',
        'type': 'state',
        'account': source_account,
        'link': dest_account,
        'balance': adjustedbal,
        'representative': rep_account,
        'previous': prev,
        'key': priv_key
    }

    try:
        log.info(timeLog("Creating block"))
        resp = requests.post(url=nodeUrl, json=params, timeout=120)
        block = resp.json()['block']
        hash = resp.json()['hash']
        if len(hash) != 64:
            log.warning(timeLog("Could not create block. %r" %e))
            return False

    except Exception as e:
        log.warning(timeLog("Could not create block. %r" %e))
        return False

    # send the transactions
    params = {
        'action': 'process',
        'block': block
    }
    try:
        log.info(timeLog("Publishing block"))
        resp = requests.post(url=nodeUrl, json=params, timeout=60)
        hash = resp.json()['hash']
        if len(hash) != 64:
            log.warning(timeLog("Could not send block. %r" %e))

    except Exception as e:
        log.warning(timeLog("Could not send block. %r" %e))
        return False

    return hash

#Push hourly averages to the blockchain
async def pushStats():
    global latestRunStatTime
    global latestGlobalBlocks
    global latestGlobalPeers
    global latestGlobalDifficulty

    latestRunStatTime = time.time() - runStatEvery # init
    startTime = time.time()

    while 1:
        await statSleep(startTime)
        startTime = time.time() #to measure the loop speed
        prev = None
        adjustedbal = None
        block = None
        hash = None

        try:
            blocks = latestGlobalBlocks.copy()
            peers = latestGlobalPeers.copy()
            diff = latestGlobalDifficulty.copy()

            # block stat
            if (len(latestGlobalBlocks) > 1):
                # remove data outside the time window used for average
                for entry in latestGlobalBlocks:
                    if (entry['time'] < time.time() - runStatEvery):
                        blocks.remove(entry)
                latestGlobalBlocks = blocks.copy()
                # calculate average cph (confirms per hour) (if positive)
                if (blocks[-1]['time'] - blocks[0]['time'] > 0):
                    cphAve = (blocks[-1]['data'] - blocks[0]['data']) / (blocks[-1]['time'] - blocks[0]['time']) * 3600
                else:
                    continue
            else:
                continue
        except Exception as e:
            log.warning(timeLog("Failed to block stat. %r" %e))
            continue

        try:
            # peer stat
            if (len(latestGlobalPeers) > 1):
                # remove data outside the time window used for average
                peersSum = 0
                for entry in latestGlobalPeers:
                    if (entry['time'] < time.time() - runStatEvery):
                        peers.remove(entry)
                    else:
                        peersSum += entry['data']
                latestGlobalPeers = peers.copy()
                # calculate average peers (if positive)
                if (peers[-1]['time'] - peers[0]['time'] > 0):
                    peersAve = peersSum / len(peers)
                else:
                    continue
            else:
                continue
        except Exception as e:
            log.warning(timeLog("Failed to peer stat. %r" %e))
            continue

        try:
            # difficulty stat
            if (len(latestGlobalDifficulty) > 1):
                # remove data outside the time window used for average
                diffSum = 0
                for entry in latestGlobalDifficulty:
                    if (entry['time'] < time.time() - runStatEvery):
                        diff.remove(entry)
                    else:
                        diffSum += entry['data']
                latestGlobalDifficulty = diff.copy()
                # calculate average difficulty (if positive)
                if (diff[-1]['time'] - diff[0]['time'] > 0):
                    diffAve = diffSum / len(diff)
                else:
                    continue
            else:
                continue

        except Exception as e:
            log.warning(timeLog("Failed to diff stat. %r" %e))
            continue

        try:
            # encode stats into strings with format 2019-10-24 00 15:49 00 <stat without decimal point and max 3 decimals>
            timeNow = str(time.time())[:10] + '00'
            cphStringVal = int(timeNow + str(round(cphAve)))
            peersStringVal = int(timeNow + str(round(peersAve)))
            diffStringVal = int(timeNow + str(round(diffAve)))

        except Exception as e:
            log.warning(timeLog("Failed to prepare stat push. %r" %e))
            continue

        try:
            hashCph = await publishStatBlock(source_account, priv_key, cph_account, rep_account, cphStringVal)
            hashPeers = await publishStatBlock(source_account, priv_key, peers_account, rep_account, peersStringVal)
            hashDiff = await publishStatBlock(source_account, priv_key, difficulty_account, rep_account, diffStringVal)

            if (hashCph):
                log.info(timeLog(hashCph))

            if (hashPeers):
                log.info(timeLog(hashPeers))

            if (hashDiff):
                log.info(timeLog(hashDiff))

        except Exception as e:
            log.warning(timeLog("Failed to stat push. %r" %e))
            continue

loop = asyncio.get_event_loop()
#PYTHON >3.7
ignore_aiohttp_ssl_error(loop) #ignore python bug

if (BETA):
    futures = [getPeers(), getAPI()]
else:
    futures = [getPeers(), getAPI(), pushStats()]
#futures = [getAPI()]
#futures = [getPeers()]
log.info(timeLog("Starting script"))

try:
    loop.run_until_complete(asyncio.wait(futures))
except KeyboardInterrupt:
    pass
