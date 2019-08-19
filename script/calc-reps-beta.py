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

"""CUSTOM VARS"""
#nodeUrl = 'http://[::1]:7076' #main
nodeUrl = 'http://[::1]:55000' #beta
logFile="repstat.log"
statFile = '/var/www/monitor/stats-beta.json' #placed in a web server for public access
monitorFile = '/var/www/monitor/monitors-beta.json' #placed in a web server for public access
activeCurrency = 'nano-beta' #nano, banano or nano-beta

"""LESS CUSTOM VARS"""
#ninjaMonitors = 'https://mynano.ninja/api/accounts/monitors' #main
ninjaMonitors = 'https://beta.mynano.ninja/api/accounts/monitors' #beta
minCount = 1 #initial required block count
timeout = 5 #http request timeout for API
runAPIEvery = 15 #run API check every X sec
runPeersEvery = 120 #run peer check every X sec
maxURLRequests = 250 #maximum concurrent requests

"""CONSTANTS"""
pLatestVersionStat = 0 #percentage running latest protocol version
pTypesStat = 0 #percentage running tcp
pStakeTotalStat = 0 #percentage connected online weight of maximum
pStakeRequiredStat = 0 #percentage of connected online weight of maxium required for voting
pStakeLatestVersionStat = 0 #percentage of connected online weight that is on latest version
peerInfo = [] #connected peers with weight info
confCountLimit = 1000 #lower limit for block count to include confirmation average
confSpanLimit = 60000 #lower limit for time span to include confirmation average

#Default starting node list. Is dynamically updated
repsInit = ['https://beta.api.nanocrawler.cc',
    'https://monitor-beta.mynano.ninja',
    'http://beta.warai.me',
    'http://benna.just-dmitry.ru',
    'https://beta.nanoskynode.com',
    'https://b.repnode.org',
    'https://nano-faucet.org/beta/monitor',
    'http://beta.nanode.cc',
    'https://json.nanoticker.info',
    'http://95.216.205.225',
    'http://kamikaze.awiki.org/betaNanoNodeMonitor'
    ]

reps = repsInit

logging.basicConfig(level=logging.INFO,filename=logFile, filemode='a', format='%(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

#Calculate median value of a list
def median(lst):
    sortedLst = sorted(lst)
    lstLen = len(lst)
    index = (lstLen - 1) // 2

    if (lstLen % 2):
        return sortedLst[index]
    else:
        return (sortedLst[index] + sortedLst[index + 1])/2.0

async def getMonitor(url):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200 and response.headers['Content-Type'] != 'application/json':
                    return
                try:
                    #ensure the content is longer than 20 chars
                    if int(response.headers['Content-Length']) < 20:
                        return
                except:
                    pass
                try:
                    r = await response.json(content_type='application/json')
                    if r['currentBlock'] > 0:
                        return r

                except Exception as e:
                    #print('Could not read json 1. Error: %r' %e)
                    pass
        except Exception as e:
            #print('Could not read API from %r. Error: %r' %(url, e))
            pass

async def verifyMonitor(url):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200 and response.headers['Content-Type'] != 'application/json':
                    return
                try:
                    #ensure the content is longer than 20 chars
                    if int(response.headers['Content-Length']) < 20:
                        return
                except:
                    pass
                try:
                    r = await response.json(content_type='application/json')
                    if r['currentBlock'] > 0:
                        url = url.replace('/api.php','')
                        return [r['nanoNodeAccount'], url]

                except Exception as e:
                    #print('Could not read json 1. Error: %r' %e)
                    pass
        except Exception as e:
            #print('Could not read API from %r. Error: %r' %(url,e))
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

async def getAPI():
    global minCount
    global pLatestVersionStat
    global pTypesStat
    global pStakeTotalStat
    global pStakeRequiredStat
    global pStakeLatestVersionStat
    global peerInfo
    global activeCurrency

    await asyncio.sleep(10) #Wait for some values to be calculated from getPeers
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
                #print('Monitor API read timeout: %r' %t)
                pass
            finally:
                for i, task in enumerate(tasks):
                    if task.done() and not task.cancelled():
                        try:
                            if task.result() is not None and task.result():
                                if task.result()['currentBlock'] > 0:
                                    jsonData.append(task.result())
                                    #print(task.result()['nanoNodeName'])
                        except Exception as e:
                            print('Could not read json for %r. Error: %r' %(task.result(),e))
                            pass

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

        #Convert all API json inputs
        fail = False #If a REP does not support one or more of the entries
        limitedReps = [] #reps not supporting all parameters
        supportedReps = [] #reps supporting all parameters

        if jsonData is None or type(jsonData[0]) == bool:
            continue
        for j in jsonData:
            if len(j) > 0:
                try:
                    count = int(j['currentBlock'])

                    #skip if the node is out of sync
                    if count < minCount:
                        continue
                except Exception as e:
                    count = 0
                    continue

                #Validate if the monitor is for nano, banano or nano-beta (if possible)
                try:
                    currency = j['currency']
                    if currency != activeCurrency:
                        continue
                except Exception as e:
                    pass

                try:
                    name = j['nanoNodeName']
                except Exception as e:
                    name = -1
                    fail = True

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
                    weight = j['votingWeight']
                except Exception as e:
                    weight = -1
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

                #read all monitor info
                countData.append(count)

                if (cemented > 0):
                    cementedData.append(cemented)
                if (unchecked > 0):
                    uncheckedData.append(unchecked)
                if (peers > 0):
                    peersData.append(peers)
                if (sync > 0):
                    syncData.append(sync)
                if (conf50 > 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf50Data.append(conf50)
                if (conf75 > 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf75Data.append(conf75)
                if (conf90 > 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf90Data.append(conf90)
                if (conf99 > 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    conf99Data.append(conf99)
                if (confAve > 0 and (confCount > confCountLimit or confSpan > confSpanLimit)):
                    confAveData.append(confAve)
                if (memory > 0):
                    memoryData.append(memory)
                if (procTime > 0):
                    procTimeData.append(procTime)

                #If weight missing, try find matching weight from peer table
                if weight < 0:
                    for p in peerInfo:
                        if str(nanoNodeAccount) == str(p['account']):
                            weight = str(int(p['weight']) / int(1000000000000000000000000000000))

                supportedReps.append({'name':name, 'nanoNodeAccount':nanoNodeAccount[0:9]+'..'+nanoNodeAccount[-5:], 'version':version, 'protocolVersion':protocolVersion, 'currentBlock':count, 'cementedBlocks':cemented,
                'unchecked':unchecked, 'numPeers':peers, 'confAve':confAve, 'confMedian':conf50, 'weight':weight, 'memory':memory, 'procTime':procTime, "supported":not fail})
                fail = False

            else:
                log.warning(timeLog("Empty json from API calls"))

        blockCountMedian = 0
        cementedMedian = 0
        uncheckedMedian = 0
        peersMedian = 0
        syncMedian = 0
        conf50Median = 0
        conf75Median = 0
        conf90Median = 0
        conf99Median = 0
        confAveMedian = 0
        memoryMedian = 0
        procTimeMedian = 0

        blockCountMax = 0
        cementedMax = 0
        uncheckedMax = 0
        peersMax = 0
        syncMax = 0
        memoryMax = 0
        procTimeMax = 0

        blockCountMin = 0
        cementedMin = 0
        uncheckedMin = 0
        peersMin = 0
        syncMin = 0
        confAveMin = 0
        memoryMin = 0
        procTimeMin = 0

        if len(countData) > 0:
            blockCountMedian = int(median(countData))
            blockCountMax = int(max(countData))
            blockCountMin = int(min(countData))
            #Update the min allowed block count
            minCount = int(blockCountMax/2)

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
        if len(syncData) > 0:
            syncMedian = float(median(syncData))
            syncMax = float(max(syncData))
            syncMin = float(min(syncData))
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
            "peersMedian":str(peersMedian),\
            "peersMax":int(peersMax),\
            "peersMin":int(peersMin),\
            "syncMedian":float(syncMedian),\
            "syncMax":float(syncMax),\
            "syncMin":float(syncMin),\
            "memoryMedian":int(memoryMedian),\
            "memoryMax":int(memoryMax),\
            "memoryMin":int(memoryMin),\
            "procTimeMedian":int(procTimeMedian),\
            "procTimeMax":int(procTimeMax),\
            "procTimeMin":int(procTimeMin),\
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
            "pLatestVersionStat":pLatestVersionStat,\
            "pTypesStat":pTypesStat,\
            "pStakeTotalStat":pStakeTotalStat,\
            "pStakeRequiredStat":pStakeRequiredStat,\
            "pStakeLatestVersionStat":pStakeLatestVersionStat,\
            "lastUpdated":str(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),\
            "lastUpdatedUnix":str(time.time()),\
            }

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
        sleep = runAPIEvery - (time.time() - startTime)
        await asyncio.sleep(sleep)

async def getPeers():
    global reps
    global pLatestVersionStat
    global pTypesStat
    global pStakeTotalStat
    global pStakeRequiredStat
    global pStakeLatestVersionStat
    global peerInfo

    while 1:
        startTime = time.time() #to measure the loop speed
        pPeers = []
        pVersions = []
        pStakeTot = 0
        pStakeReq = 0
        pStakeLatest = 0
        supply = 133248061996216572282917317807824970865

        log.info(timeLog("Verifying peers"))
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
                    """
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
                    """

                    #Read protocol version and type
                    pVersions.append(value['protocol_version'])
                    pPeers.append({"ip":ipv6, "version":value["protocol_version"], "type":value["type"], "weight":0, "account": ""})

        except Exception as e:
            log.warning(timeLog("Could not read peers from node RPC. %r" %e))
            sleep = runPeersEvery - (time.time() - startTime)
            await asyncio.sleep(sleep)
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
                #print('Monitor API read timeout: %r' %t)
                pass
            finally:
                for i, task in enumerate(tasks):
                    if task.done() and not task.cancelled():
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
                                    #print("Valid"+task.result()[1])
                                    validPaths.append(task.result()[1])
                                repAccounts.append(task.result()[0])

                        except Exception as e:
                            print('Could not read json for %r. Error: %r' %(task.result(),e))
                            pass

        #Update the final list
        reps = validPaths.copy()
        log.info(reps)

        sleep = runPeersEvery - (time.time() - startTime)
        await asyncio.sleep(sleep)

loop = asyncio.get_event_loop()
#PYTHON >3.7
ignore_aiohttp_ssl_error(loop) #ignore python bug

futures = [getPeers(), getAPI()]
#futures = [getAPI()]
#futures = [getPeers()]
log.info(timeLog("Starting script"))

try:
    loop.run_until_complete(asyncio.wait(futures))
except KeyboardInterrupt:
    pass
