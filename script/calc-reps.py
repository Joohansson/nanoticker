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
import websockets
import numpy as np
from pathlib import Path
from decimal import Decimal
from collections import deque #for array shifting

#Own references
import repList

"""CUSTOM VARS"""
BETA = False #SET TO False FOR MAIN NET
DEV = False #SET TO True when developing

if DEV:
    nodeUrl = 'http://127.0.0.1:55000'
    telemetryAddress = '127.0.0.1'
    telemetryPort = '7075'
    websocketAddress  = 'ws://127.0.0.1:54321'
    logFile="repstat.log"
    statFile = 'stats.json' #placed in a web server for public access
    monitorFile = 'monitors.json' #placed in a web server for public access
    activeCurrency = 'nano' #nano, banano or nano-beta
    ninjaMonitors = 'https://mynano.ninja/api/accounts/monitors'
    aliasUrl = 'https://mynano.ninja/api/accounts/aliases'
    localTelemetryAccount = 'nano_3jsonxwips1auuub94kd3osfg98s6f4x35ksshbotninrc1duswrcauidnue' #telemetry is retrived with another command for this account
    websocketPeerDropLimit = 60 #telemetry data from nodes not reported withing this interval (seconds) will be dropped from the list (until they report again)

elif BETA:
    nodeUrl = 'http://127.0.0.1:55000' #beta
    telemetryAddress = '127.0.0.1'
    telemetryPort = '54000'
    websocketAddress  = 'ws://127.0.0.1:57000'
    logFile="/root/betanode/repstat.log"
    statFile = '/root/scripts/nginx/html/repstat-beta/json/stats-beta.json' #placed in a web server for public access
    monitorFile = '/root/scripts/nginx/html/repstat-beta/json/monitors-beta.json' #placed in a web server for public access
    activeCurrency = 'nano-beta' #nano, banano or nano-beta
    ninjaMonitors = 'https://beta.mynano.ninja/api/accounts/monitors' #beta
    aliasUrl = ''
    localTelemetryAccount = 'nano_1json51qn9t7cqebcds1b7f9t3cffbki7qanudqpo67xcpowpt1org1p9rus' #telemetry is retrived with another command for this account
    websocketPeerDropLimit = 60 #telemetry data from nodes not reported withing this interval (seconds) will be dropped from the list (until they report again)

else:
    nodeUrl = 'http://[::1]:7076' #main
    telemetryAddress = '127.0.0.1'
    telemetryPort = '7075'
    websocketAddress  = 'ws://[::1]:54321'
    logFile="/root/logs/repstat.log"
    statFile = '/root/scripts/nginx/html/repstat/json/stats.json' #placed in a web server for public access
    monitorFile = '/root/scripts/nginx/html/repstat/json/monitors.json' #placed in a web server for public access
    activeCurrency = 'nano' #nano, banano or nano-beta
    ninjaMonitors = 'https://mynano.ninja/api/accounts/monitors'
    aliasUrl = 'https://mynano.ninja/api/accounts/aliases'
    localTelemetryAccount = 'nano_1iuz18n4g4wfp9gf7p1s8qkygxw7wx9qfjq6a9aq68uyrdnningdcjontgar' #telemetry is retrived with another command for this account
    websocketPeerDropLimit = 180 #telemetry data from nodes not reported withing this interval (seconds) will be dropped from the list (until they report again)

# Speed test source account
workUrl = 'http://127.0.0.1:9971'
workDiff = 'fffffff800000000' # 1x
source_account = ''
priv_key = ''
speedtest_rep = ''
speedtest_websocket_1 = '' # Preferably in another country
speedtest_websocket_2 = '' # Leave blank if you don't have one
speedtest_websocket_ping_offset_1 = 45 #ping/2 ms latency for the websocket node to be deducted from the speed delay
speedtest_websocket_ping_offset_2 = 20 #ping/2 ms latency for the websocket node to be deducted from the speed delay


# For pushing stats to the blockchain (no longer used)
# source_account = 'nano_1ticker1j6fax9ke4jajppaj6gcuhfys9sph3hhprq3ewj31z4qndbcb5feq'
# rep_account = 'nano_1iuz18n4g4wfp9gf7p1s8qkygxw7wx9qfjq6a9aq68uyrdnningdcjontgar'
# priv_key = ''
# cph_account = 'nano_1cph1t1yp3nb9wq3zkh6q69yxq5ikwz4rt3jiy9kqxdmbyjz48shrmt9neyn'
# peers_account = 'nano_1peers1jrgie5gji5oasgi5zawc1bjb9r138e88g4ia9to56dih7sp5p19xy'
# difficulty_account = 'nano_1diff1tojcgttgewe1pkm4yyjwbbb51oewbro3wtsnxjrtz5i9iuuq3f4frt'

"""LESS CUSTOM VARS"""
minCount = 1 #initial required block count
monitorTimeout = 8 #http request timeout for monitor API
rpcTimeout = 8 #node rpc timeout

runAPIEvery = 10 #run API check (at fastest) every X sec (the websocket on beta runs every 18sec and main every 60)
runPeersEvery = 120 #run peer check every X sec
runStatEvery = 3600 #publish stats to blockchain every x sec
maxURLRequests = 250 #maximum concurrent requests
websocketCountDownLimit = 1 #call API if x sec has passed since last websocket message
runSpeedTestEvery = 120 #run speed test every X sec

"""CONSTANTS"""
pLatestVersionStat = 0 #percentage running latest protocol version
pTypesStat = 0 #percentage running tcp
pStakeTotalStat = 0 #percentage connected online weight of maximum
pStakeRequiredStat = 0 #percentage of connected online weight of maxium required for voting
pStakeLatestVersionStat = 0 #percentage of connected online weight that is on latest version
confCountLimit = 100 #lower limit for block count to include confirmation average
confSpanLimit = 10000 #lower limit for time span to include confirmation average

if BETA:
    repsInit = repList.repsInitB
    blacklist = repList.blacklistB
    checkCPSEvery = 1 #inverval for calculating BPS/CPS from telemetry. Total time is runAPIEvery * checkCPSEvery
else:
    repsInit = repList.repsInitM
    blacklist = repList.blacklistM
    checkCPSEvery = 1 #inverval for calculating BPS/CPS from telemetry. Total time is runAPIEvery * checkCPSEvery

"""VARIABLES"""
reps = repsInit
latestOnlineWeight = 0 #used for calculating PR status
latestRunStatTime = 0 #fine tuning loop time for stats
latestGlobalBlocks = []
latestGlobalPeers = []
latestGlobalDifficulty = []

# For BPS/CPS calculations (array with previous values to get a rolling window)
previousMaxBlockCount = deque([0]*checkCPSEvery)
previousMaxConfirmed = deque([0]*checkCPSEvery)
previousMedianBlockCount = deque([0]*checkCPSEvery)
previousMedianConfirmed = deque([0]*checkCPSEvery)
previousMedianTimeStamp = deque([0]*checkCPSEvery)
previousMaxBlockCount_pr = deque([0]*checkCPSEvery)
previousMaxConfirmed_pr = deque([0]*checkCPSEvery)
previousMedianBlockCount_pr = deque([0]*checkCPSEvery)
previousMedianConfirmed_pr = deque([0]*checkCPSEvery)
previousMedianTimeStamp_pr = deque([0]*checkCPSEvery)

previousLocalTimeStamp = deque([0]*checkCPSEvery)
previousLocalMax = deque([0]*checkCPSEvery)
previousLocalCemented = deque([0]*checkCPSEvery)

# individual BPS CPS object
indiPeersPrev = {'ip':{}}

# IPs that has a monitor. To get rid of duplicates in telemetry
monitorIPExistArray = {'ip':{}}

# account / alias pairs
aliases = []

# Websocket control timer for when to call monitor API
websocketTimer = time.time()
websocketCountDownTimer = time.time()
startTime = time.time()
apiShouldCall = False

# speed test memory
speedtest_latest = []
speedtest_latest_ms = [0]
speedtest_last_valid = time.time()

filename = Path(logFile)
filename.touch(exist_ok=True)
logging.basicConfig(level=logging.INFO,filename=logFile, filemode='a+', format='%(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

#Calculate the average value of the 50% middle percentile from a list
def median(lst):
    try:
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
    except Exception as e:
        log.warning(timeLog("Could not calculate median value. %r" %e))

def medianNormal(lst):
    sortedLst = sorted(lst)
    lstLen = len(lst)
    index = (lstLen - 1) // 2

    if (lstLen % 2):
        return sortedLst[index]
    else:
        return (sortedLst[index] + sortedLst[index + 1])/2.0

async def fetch(session, url):
    try:
        async with session.get(url) as response:
            try:
                if (response.status == 200):
                    r = await response.text()
                    return r
            except:
                pass
    except:
        pass

async def getMonitor(url):
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            r = await fetch(session, url)
            try:
                rjson = json.loads(r)
                if int(rjson['currentBlock']) > 0:
                    return [rjson, True, url, time.time(), r]
            except:
                return [{}, False, url, time.time(), r]
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

async def getTelemetryRPC(params, ipv6):
    try:
        async with aiohttp.ClientSession(json_serialize=json.dumps, connector=aiohttp.TCPConnector(ssl=False)) as session:
            try:
                callTime = time.time()
                timeDiff = 0
                r = None
                r = await session.post(nodeUrl, json=params)
                j = await r.json()
                timeDiff = round((time.time()-callTime)*1000) #request time
                return [j, True, params['address'], ipv6, timeDiff, time.time(), r]
            except:
                log.warning(timeLog("Bad telemtry response from node. Probably timeout."))
                return [{}, False, params['address'], ipv6, 0, time.time(), r]
    except:
        pass

async def getRegularRPC(params):
    try:
        with async_timeout.timeout(rpcTimeout):
            async with aiohttp.ClientSession(json_serialize=json.dumps, connector=aiohttp.TCPConnector(ssl=False)) as session:
                try:
                    callTime = time.time()
                    timeDiff = 0
                    r = None
                    r = await session.post(nodeUrl, json=params)
                    j = await r.json()
                    timeDiff = round((time.time()-callTime)*1000) #request time
                    return [j, True, timeDiff, r]

                except:
                    log.warning(timeLog("Bad rpc response from node. Probably timeout."))
                    return [{}, False, timeDiff, r]

    except asyncio.TimeoutError as t:
        log.warning(timeLog("RPC communication timed out"))
        pass
    except:
        pass

# Each websocket message will reset the timer and when enough time has passed between two messages the API function is called and timer reset
async def websocketCountDown():
    global websocketTimer
    global websocketCountDownTimer
    global apiShouldCall

    while 1:
        if apiShouldCall and time.time() > websocketCountDownTimer + websocketCountDownLimit:
            # if enough time has passed since last run
            if time.time() > websocketTimer + runAPIEvery:
                websocketTimer = time.time() # reset timer
                websocketCountDownTimer = time.time() # reset timer
                apiShouldCall = False
                await getAPI()
        await asyncio.sleep(0.1)

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
    if sleep < 0:
        sleep = 0
    await asyncio.sleep(sleep)

async def peerSleep(startTime):
    sleep = runPeersEvery - (time.time() - startTime)
    if sleep < 0:
        sleep = 0
    await asyncio.sleep(sleep)

async def statSleep(startTime):
    global latestRunStatTime

    sleep = runStatEvery - (time.time() - startTime) - (time.time() - round(latestRunStatTime/10)*10 - runStatEvery)
    latestRunStatTime = time.time()
    if sleep < 0:
        sleep = 0
    await asyncio.sleep(sleep)

async def getAPI():
    global minCount
    global pLatestVersionStat
    global pTypesStat
    global pStakeTotalStat
    global pStakeRequiredStat
    global pStakeLatestVersionStat
    global activeCurrency
    global latestGlobalBlocks
    global latestGlobalPeers
    global latestGlobalDifficulty
    global previousMaxBlockCount
    global previousMaxConfirmed
    global previousMedianBlockCount
    global previousMedianConfirmed
    global previousMedianTimeStamp
    global previousMaxBlockCount_pr
    global previousMaxConfirmed_pr
    global previousMedianBlockCount_pr
    global previousMedianConfirmed_pr
    global previousMedianTimeStamp_pr
    global previousLocalMax
    global previousLocalCemented
    global previousLocalTimeStamp
    global indiPeersPrev
    global startTime
    global speedtest_latest_ms

    PRStatusLocal = False

    telemetryPeers = []

    # GET TELEMETRY FOR LOCAL ACCOUNT (can't use normal telemetry)
    try:
        apiStartTime = time.time()

        # get block count
        params = {
            "action": "telemetry",
            "address": telemetryAddress,
            "port": telemetryPort
        }
        resp = await getRegularRPC(params)
        telemetry = resp[0]

        block_count_tele = -1
        cemented_count_tele = -1
        unchecked_count_tele = -1
        account_count_tele = -1
        bandwidth_cap_tele = -1
        peer_count_tele = -1
        protocol_version_number_tele = -1
        major_version_tele = -1
        minor_version_tele = -1
        patch_version_tele = -1
        pre_release_version_tele = -1
        uptime_tele = -1
        timeStamp_tele = time.time()
        weight = -1
        PRStatus = False

        # calculate max/min/medians using telemetry data. Init first
        countData = []
        cementedData = []
        uncheckedData = []
        peersData = []
        peerHasEnoughBlocks = False

        if 'block_count' in telemetry:
            block_count_tele = int(telemetry['block_count'])
            if block_count_tele >= minCount: #only add to stats if above limit
                peerHasEnoughBlocks = True
                countData.append(block_count_tele)
        if peerHasEnoughBlocks:
            if 'timestamp' in telemetry:
                timeStamp_tele = int(telemetry['timestamp'])
            if 'cemented_count' in telemetry:
                cemented_count_tele = int(telemetry['cemented_count'])
                cementedData.append(cemented_count_tele)
            if 'unchecked_count' in telemetry:
                unchecked_count_tele = int(telemetry['unchecked_count'])
                uncheckedData.append(unchecked_count_tele)
            if 'account_count' in telemetry:
                account_count_tele = int(telemetry['account_count'])
            if 'bandwidth_cap' in telemetry:
                bandwidth_cap_tele = telemetry['bandwidth_cap']
            if 'peer_count' in telemetry:
                peer_count_tele = int(telemetry['peer_count'])
                peersData.append(peer_count_tele)
            if 'protocol_version' in telemetry:
                protocol_version_number_tele = int(telemetry['protocol_version'])
            if 'major_version' in telemetry:
                major_version_tele = telemetry['major_version']
            if 'minor_version' in telemetry:
                minor_version_tele = telemetry['minor_version']
            if 'patch_version' in telemetry:
                patch_version_tele = telemetry['patch_version']
            if 'pre_release_version' in telemetry:
                pre_release_version_tele = telemetry['pre_release_version']
            if 'uptime' in telemetry:
                uptime_tele = telemetry['uptime']

            BPSLocal = -1
            if block_count_tele > 0 and previousLocalMax[0] > 0 and (timeStamp_tele - previousLocalTimeStamp[0]) > 0 and previousLocalTimeStamp[0] > 0:
                BPSLocal = (block_count_tele - previousLocalMax[0]) / (timeStamp_tele - previousLocalTimeStamp[0])
            CPSLocal = -1
            if cemented_count_tele > 0 and previousLocalCemented[0] > 0 and (timeStamp_tele - previousLocalTimeStamp[0]) > 0 and previousLocalTimeStamp[0] > 0:
                CPSLocal = (cemented_count_tele - previousLocalCemented[0]) / (timeStamp_tele - previousLocalTimeStamp[0])

            # ms to sec (if reported in ms)
            if timeStamp_tele > 9999999999 and previousLocalTimeStamp[0] > 9999999999 and BPSLocal != -1:
                BPSLocal = BPSLocal * 1000
                CPSLocal = CPSLocal * 1000

            if timeStamp_tele > 0:
                previousLocalTimeStamp.append(timeStamp_tele)
                previousLocalTimeStamp.popleft()
            if block_count_tele > 0:
                previousLocalMax.append(block_count_tele)
                previousLocalMax.popleft()
            if cemented_count_tele > 0:
                previousLocalCemented.append(cemented_count_tele)
                previousLocalCemented.popleft()

            #get weight
            params = {
                "action": "account_weight",
                "account": localTelemetryAccount
            }
            reqTime = '0'
            try:
                resp_weight = await getRegularRPC(params)
                reqTime = resp_weight[2]
                if 'weight' in resp_weight[0]:
                    weight = int(resp_weight[0]['weight']) / int(1000000000000000000000000000000)
                    if (weight >= latestOnlineWeight*0.001):
                        PRStatus = True
                        PRStatusLocal = True #used for comparing local BPS/CPS with the rest
                    else:
                        PRStatus = False
            except Exception as e:
                log.warning(timeLog("Could not read local weight from node RPC. %r" %e))
                pass

            teleTemp = {"ip":'', "protocol_version":protocol_version_number_tele, "type":"", "weight":weight, "account": localTelemetryAccount,
            "block_count":block_count_tele, "cemented_count":cemented_count_tele, "unchecked_count":unchecked_count_tele,
            "account_count":account_count_tele, "bandwidth_cap":bandwidth_cap_tele, "peer_count":peer_count_tele, "bps":BPSLocal, "cps":CPSLocal,
            "vendor_version":str(major_version_tele) + '.' + str(minor_version_tele) + '.' + str(patch_version_tele) + '.' + str(pre_release_version_tele), "uptime":uptime_tele, "PR":PRStatus, "req_time":reqTime, "time_stamp":timeStamp_tele,
            "tsu": 0}

            telemetryPeers.append(teleTemp) # add local account rep

    except Exception as e:
        log.warning(timeLog("Could not read local telemetry from node RPC. %r" %e))
        pass

    # GET TELEMETRY DATA FROM PEERS

    #PR ONLY
    countData_pr = []
    cementedData_pr = []
    uncheckedData_pr = []
    peersData_pr = []

    try:
        block_count_tele = -1
        cemented_count_tele = -1
        unchecked_count_tele = -1
        account_count_tele = -1
        bandwidth_cap_tele = -1
        peer_count_tele = -1
        protocol_version_number_tele = -1
        major_version_tele = -1
        minor_version_tele = -1
        patch_version_tele = -1
        pre_release_version_tele = -1
        uptime_tele = -1
        timeStamp_tele = time.time()
        address_tele = ''
        port_tele = ''
        BPSPeer = -1
        CPSPeer = -1
        tsuDiff = 0

        # Use the latest updated data from telemetry websocket
        indiPeersPrevCopy = dict(indiPeersPrev)
        for key in indiPeersPrevCopy:
            peerHasEnoughBlocks = False
            if key == 'ip':
                continue
            metric = indiPeersPrevCopy[key]

            # drop peer from the list if too old
            if 'timestamp_local' in metric:
                timestamp_local_tele = metric['timestamp_local'] + websocketCountDownLimit + (time.time() - apiStartTime)
                tsuDiff = time.time() - timestamp_local_tele
                if time.time() > timestamp_local_tele + websocketPeerDropLimit:
                    del indiPeersPrev[key]
                    log.info(timeLog("Dropping peer telemetry data due to inactivity: " + key))
                    continue

            if 'blockCount' in metric:
                block_count_tele = int(metric['blockCount'][-1])
                if block_count_tele >= minCount: #only add to stats if above limit
                    peerHasEnoughBlocks = True
                    countData.append(block_count_tele)

            if peerHasEnoughBlocks:
                if 'timestamp' in metric:
                    timeStamp_tele = int(metric['timestamp'][-1])

                if 'cementCount' in metric:
                    cemented_count_tele = int(metric['cementCount'][-1])
                    cementedData.append(cemented_count_tele)

                if 'unchecked_count' in metric:
                    unchecked_count_tele = int(metric['unchecked_count'])
                    uncheckedData.append(unchecked_count_tele)

                if 'account_count' in metric:
                    account_count_tele = int(metric['account_count'])
                if 'bandwidth_cap' in metric:
                    bandwidth_cap_tele = metric['bandwidth_cap']
                if 'peer_count' in metric:
                    peer_count_tele = int(metric['peer_count'])
                    peersData.append(peer_count_tele)
                if 'protocol_version' in metric:
                    protocol_version_number_tele = int(metric['protocol_version'])
                if 'major_version' in metric:
                    major_version_tele = metric['major_version']
                if 'minor_version' in metric:
                    minor_version_tele = metric['minor_version']
                if 'patch_version' in metric:
                    patch_version_tele = metric['patch_version']
                if 'pre_release_version' in metric:
                    pre_release_version_tele = metric['pre_release_version']
                if 'uptime' in metric:
                    uptime_tele = metric['uptime']
                if 'address' in metric:
                    address_tele = metric['address']
                if 'port' in metric:
                    port_tele = metric['port']
                if 'bps' in metric:
                    BPSPeer = metric['bps']
                if 'cps' in metric:
                    CPSPeer = metric['cps']

                teleTemp = {"ip":'['+address_tele+']:'+port_tele, "protocol_version":protocol_version_number_tele, "type":"", "weight":-1, "account": "",
                "block_count":block_count_tele, "cemented_count":cemented_count_tele, "unchecked_count":unchecked_count_tele,
                "account_count":account_count_tele, "bandwidth_cap":bandwidth_cap_tele, "peer_count":peer_count_tele, "bps":BPSPeer, "cps":CPSPeer,
                "vendor_version":str(major_version_tele) + '.' + str(minor_version_tele) + '.' + str(patch_version_tele) + '.' + str(pre_release_version_tele), "uptime":uptime_tele, "PR":False, "req_time":'0', "time_stamp":timeStamp_tele,
                "tsu": tsuDiff}

                telemetryPeers.append(teleTemp)

    except Exception as e:
        log.warning(timeLog("Could not read raw telemetry from node RPC. %r" %e))
        pass

    # GET WEIGHT FROM CONFIRMATION QUORUM
    params = {
        "action": "confirmation_quorum",
        "peer_details": True,
    }
    try:
        resp = await getRegularRPC(params)

        #Find matching IP and include weight in original peer list
        if 'peers' in resp[0]:
            for peer in resp[0]['peers']:
                for i,cPeer in enumerate(telemetryPeers):
                    if peer['ip'] == cPeer['ip'] and peer['ip'] != '':
                        # append the relevant PR stats here as well
                        weight = peer['weight']
                        if weight != -1: #only update if it has been given
                            weight = int(weight) / int(1000000000000000000000000000000)
                            if (weight >= latestOnlineWeight*0.001):
                                PRStatus = True
                                if cPeer['block_count'] != -1:
                                    countData_pr.append(int(cPeer['block_count']))
                                if cPeer['cemented_count'] != -1:
                                    cementedData_pr.append(int(cPeer['cemented_count']))
                                if cPeer['unchecked_count'] != -1:
                                    uncheckedData_pr.append(int(cPeer['unchecked_count']))
                                if cPeer['peer_count'] != -1:
                                    peersData_pr.append(int(cPeer['peer_count']))
                            else:
                                PRStatus = False

                        telemetryPeers[i] = dict(cPeer, **{"weight": weight, "account": peer['account'], "PR":PRStatus}) #update previous vaule
                        continue

    except Exception as e:
        log.warning(timeLog("Could not read quorum from node RPC. %r" %e))
        pass

    # Append the BPS CPS data
    bpsData = []
    cpsData = []
    bpsData_pr = []
    cpsData_pr = []

    # Append bandwidth data
    bwData = []
    bwData_pr = []

    try:
        # Also include block_count to determine correct max values later
        for p in telemetryPeers:
            if p['bps'] != -1 and p['block_count'] != -1:
                #skip if the node is out of sync
                if int(p['block_count']) < minCount:
                    continue

                list = [float(p['bps']), int(p['block_count'])]
                bpsData.append(list)
                if (p['PR'] == True):
                    bpsData_pr.append(list)

            if p['cps'] != -1  and p['cemented_count'] != -1:
                list = [float(p['cps']), int(p['cemented_count'])]
                cpsData.append(list)
                if (p['PR'] == True):
                    cpsData_pr.append(list)

            if p['bandwidth_cap'] != -1:
                bw = int(p['bandwidth_cap'])
                bwData.append(bw)
                if (p['PR'] == True):
                    bwData_pr.append(bw)

    except Exception as e:
        log.warning(timeLog("Could not append BPS and CPS data. %r" %e))
        pass

    # GET MONITOR DATA
    #log.info(timeLog("Get API"))
    jsonData = []
    """Split URLS in max X concurrent requests"""
    for chunk in chunks(reps, maxURLRequests):
        tasks = []
        for path in chunk:
            if len(path) > 6:
                if path[-4:] != '.htm':
                    tasks.append(asyncio.ensure_future(getMonitor('%s/api.php' %path)))
                else:
                    tasks.append(asyncio.ensure_future(getMonitor(path)))

        try:
            with async_timeout.timeout(monitorTimeout):
                await asyncio.gather(*tasks)

        except asyncio.TimeoutError as t:
            #log.warning(timeLog('Monitor API read timeout: %r' %t))
            pass
        except Exception as e:
            log.warning(timeLog(e))

        for i, task in enumerate(tasks):
            try:
                if task.result() is not None and task.result():
                    if (task.result()[1]):
                        jsonData.append([task.result()[0], task.result()[3]])
                        #log.info(timeLog('Valid: ' + task.result()[0]['nanoNodeName']))
                    else:
                        log.warning(timeLog('Could not read json from %s. Result: %s' %(task.result()[2], task.result()[4])))

            except Exception as e:
                #for example when tasks timeout
                log.warning(timeLog('Could not read response. Error: %r' %e))
                pass

            finally:
                if task.done() and not task.cancelled():
                    task.exception()  # this doesn't raise anything, just mark exception retrieved

    syncData = []
    conf50Data = []
    conf75Data = []
    conf90Data = []
    conf99Data = []
    confAveData = []
    memoryData = []
    procTimeData = []
    multiplierData = []
    monitorCount = 0

    #PR ONLY
    syncData_pr = []
    conf50Data_pr = []
    conf75Data_pr = []
    conf90Data_pr = []
    conf99Data_pr = []
    confAveData_pr = []
    memoryData_pr = []
    procTimeData_pr = []
    multiplierData_pr = []
    monitorCount_pr = 0

    tsu = -1 # time since update not valid for node monitors

    #Convert all API json inputs
    fail = False #If a REP does not support one or more of the entries
    supportedReps = [] #reps supporting all parameters
    telemetryReps = [] #reps collected with telemetry

    try:
        if jsonData is None or type(jsonData[0][0]) == bool:
            #log.info(timeLog('type error'))
            return

    except:
        return

    for js in jsonData:
        j = js[0]
        if len(j) > 0:
            isTelemetryMatch = False
            monitorCount += 1
            try:
                count = int(j['currentBlock'])

                #skip if the node is out of sync
                if count < minCount:
                    continue
            except Exception as e:
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
                storeVendor = j['store_vendor']
            except Exception as e:
                storeVendor = -1
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

            bps = -1
            cps = -1
            bw = -1

            try:
                #Match IP and replace weight and telemetry data
                skipPeer = False
                for p in telemetryPeers:
                    # first check if the account exist in the monitorIPExistArray (monitors whose URL was guessed from IP)
                    tempIP = p['ip']
                    ipFound = False
                    if tempIP != "":
                        if '[::ffff:' in tempIP: #ipv4
                            tempIP = re.search('ffff:(.*)\]:', tempIP).group(1)

                        for ip in monitorIPExistArray:
                            if tempIP == ip and monitorIPExistArray[ip]['account'] == str(nanoNodeAccount): #include this
                                ipFound = True
                                break

                    if str(nanoNodeAccount) == str(p['account']) or ipFound:
                        if int(p['weight']) != -1: #only update if it has been given
                            weight = int(p['weight'])

                        #telemetry
                        if p['vendor_version'] != -1:
                            version = p['vendor_version']
                        if p['protocol_version'] != -1:
                            protocolVersion = int(p['protocol_version'])
                        if p['block_count'] != -1:
                            #skip if the node is out of sync
                            if int(p['block_count']) < minCount:
                                skipPeer = True

                            isTelemetryMatch = True #only show as telemetry if there are actual data available
                            count = int(p['block_count'])
                        if p['cemented_count'] != -1:
                            cemented = int(p['cemented_count'])
                        if p['unchecked_count'] != -1:
                            unchecked = int(p['unchecked_count'])
                        if p['peer_count'] != -1:
                            peers = int(p['peer_count'])
                        if int(p['req_time']) >= 0:
                            procTime = int(p['req_time'])
                        if p['bps'] != -1:
                            bps = float(p['bps'])
                        if p['cps'] != -1:
                            cps = float(p['cps'])
                        if p['tsu'] != -1:
                            tsu = float(p['tsu'])
                        if p['bandwidth_cap'] != -1:
                            bw = int(p['bandwidth_cap'])
                        if p['PR'] == True:
                            PRStatus = True
                            monitorCount_pr += 1
                        else:
                            PRStatus = False
                        break

            except Exception as e:
                log.warning(timeLog("Could not match ip and replace weight and telemetry data. %r" %e))
                pass

            #skip if the node is out of sync
            try:
                if skipPeer == True:
                    continue

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

                # combined reps from monitors and telemetry data
                nanoAccount = nanoNodeAccount
                if (nanoAccount and nanoAccount != -1):
                    nanoAccount = nanoAccount.replace('xrb_','nano_')
                supportedReps.append({'name':name, 'nanoNodeAccount':nanoAccount,
                'version':version, 'protocolVersion':protocolVersion, 'storeVendor':storeVendor, 'currentBlock':count, 'cementedBlocks':cemented,
                'unchecked':unchecked, 'numPeers':peers, 'confAve':confAve, 'confMedian':conf50, 'weight':weight, 'bps':bps, 'cps':cps,
                'memory':memory, 'procTime':procTime, 'multiplier':multiplier, 'supported':not fail, 'PR':PRStatus, 'isTelemetry':isTelemetryMatch,
                'bandwidthCap':bw, 'tsu':tsu})
                fail = False

            except Exception as e:
                log.warning(timeLog("Could not append supported rep. %r" %e))
                pass

        else:
            log.warning(timeLog("Empty json from API calls"))

    # all telemetry peers that was not matched already
    try:
        for teleRep in telemetryPeers:
            found = False
            for supRep in supportedReps:
                if teleRep['account'] == supRep['nanoNodeAccount']: #do not include this
                    found = True
                    break

            # do not include telemetry IPs that was found by the monitor path guessing
            tempIP = teleRep['ip']
            if tempIP != "":
                if '[::ffff:' in tempIP: #ipv4
                    tempIP = re.search('ffff:(.*)\]:', tempIP).group(1)

                for ip in monitorIPExistArray:
                    if tempIP == ip: #do not include this
                        found = True
                        break

            if not found:
                #skip if the node is out of sync
                if int(teleRep['block_count']) < minCount:
                    continue

                # check if alias exist and use that instead of IP
                aliasSet = False
                for aliasAccount in aliases:
                    if not 'account' in aliasAccount or not 'alias' in aliasAccount:
                        continue
                    if aliasAccount['account'] == teleRep['account']:
                        ip = aliasAccount['alias']
                        if ip == '':
                            ip = 'No Name'
                        aliasSet = True
                        break

                # extract ip
                if not aliasSet:
                    if teleRep['ip'] != "":
                        if '[::ffff:' in teleRep['ip']: #ipv4
                            ip = re.search('ffff:(.*)\]:', teleRep['ip']).group(1)
                            ip = ip.split('.')[0] + '.x.x.' + ip.split('.')[3]
                        else: #ipv6
                            ip = '[' + re.search('\[(.*)\]:', teleRep['ip']).group(1) +']'
                    else:
                        ip = ""

                tempRep = {'name':ip, 'nanoNodeAccount':teleRep['account'],
                'version':teleRep['vendor_version'], 'protocolVersion':teleRep['protocol_version'], 'storeVendor':'', 'currentBlock':teleRep['block_count'], 'cementedBlocks':teleRep['cemented_count'],
                'unchecked':teleRep['unchecked_count'], 'numPeers':teleRep['peer_count'], 'confAve':-1, 'confMedian':-1, 'weight':teleRep['weight'], 'bps':teleRep['bps'], 'cps':teleRep['cps'],
                'memory':-1, 'procTime':teleRep['req_time'], 'multiplier':-1, 'supported':True, 'PR':teleRep['PR'], 'isTelemetry':True, 'bandwidthCap':teleRep['bandwidth_cap'], 'tsu':teleRep['tsu']}
                telemetryReps.append(tempRep)
    except Exception as e:
        log.warning(timeLog("Could not extract non matched telemetry reps. %r" %e))

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

    telemetryCount = 0
    BPSMax = 0
    BPSMedian = 0
    BPSp75 = 0
    CPSMax = 0
    CPSMedian = 0
    CPSp75 = 0

    bwLimit1 = 0
    bwLimit10 = 0
    bwLimit25 = 0
    bwLimit50 = 0
    bwLimit75 = 0
    bwLimit90 = 0
    bwLimit99 = 0

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

    telemetryCount_pr = 0
    BPSMax_pr = 0
    BPSMedian_pr = 0
    BPSp75_pr = 0
    CPSMax_pr = 0
    CPSMedian_pr = 0
    CPSp75_pr = 0

    bwLimit1_pr = 0
    bwLimit10_pr = 0
    bwLimit25_pr = 0
    bwLimit50_pr = 0
    bwLimit75_pr = 0
    bwLimit90_pr = 0
    bwLimit99_pr = 0

    statData = None

    # calculate number of telemetry peers
    try:
        for p in telemetryPeers:
            if (p['PR']):
                telemetryCount_pr += 1
            else:
                telemetryCount += 1
    except Exception as e:
        log.warning(timeLog("Could not calculate number of telemetry peers. %r" %e))

    # non pr is the total combined number
    telemetryCount = telemetryCount + telemetryCount_pr

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

        # treat bps and cps a bit different. the max must only be taken from the peer with max block count
        medianArray = []
        if len(bpsData) > 0:
            for data in bpsData:
                medianArray.append(data[0]) # add the bps
                # find the matching max block count and use that bps as max (even if it's technically not max). It's to avoid bootstrapping result
                if (data[1] == blockCountMax):
                    BPSMax = data[0]

            BPSMedian = float(median(medianArray))
            BPSp75 = float(np.percentile(medianArray, 75))

        medianArray = []
        if len(cpsData) > 0:
            for data in cpsData:
                medianArray.append(data[0]) # add the bps
                # find the matching max block count and use that cps as max (even if it's technically not max). It's to avoid bootstrapping result
                if (data[1] == cementedMax):
                    CPSMax = data[0]

            CPSMedian = float(median(medianArray))
            CPSp75 = float(np.percentile(medianArray, 75))

        # Bandwidth limit percentiles (replace 0 with 10Gbit/s because it count as unlimited)
        medianArray = []
        if len(bwData) > 0:
            for data in bwData:
                if data == 0:
                    data = 1250000000
                medianArray.append(data)
            bwLimit1 = int(np.percentile(medianArray, 1))
            bwLimit10 = int(np.percentile(medianArray, 10))
            bwLimit25 = int(np.percentile(medianArray, 25))
            bwLimit50 = int(np.percentile(medianArray, 50))
            bwLimit75 = int(np.percentile(medianArray, 75))
            bwLimit90 = int(np.percentile(medianArray, 90))
            bwLimit99 = int(np.percentile(medianArray, 99))

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

        # treat bps and cps a bit different. the max must only be taken from the peer with max block count
        medianArray = []
        if len(bpsData_pr) > 0:
            for data in bpsData_pr:
                medianArray.append(data[0]) # add the bps
                # find the matching max block count and use that bps as max (even if it's technically not max). It's to avoid bootstrapping result
                if (data[1] == blockCountMax_pr):
                    BPSMax_pr = data[0]

            BPSMedian_pr = float(median(medianArray))
            BPSp75_pr = float(np.percentile(medianArray, 75))

        medianArray = []
        if len(cpsData_pr) > 0:
            for data in cpsData_pr:
                medianArray.append(data[0]) # add the bps
                # find the matching max block count and use that bps as max (even if it's technically not max). It's to avoid bootstrapping result
                if (data[1] == cementedMax_pr):
                    CPSMax_pr = data[0]

            CPSMedian_pr = float(median(medianArray))
            CPSp75_pr = float(np.percentile(medianArray, 75))

        # Bandwidth limit percentiles (replace 0 with 10Gbit/s because it count as unlimited)
        medianArray = []
        if len(bwData_pr) > 0:
            for data in bwData_pr:
                if data == 0:
                    data = 1250000000
                medianArray.append(data)
            bwLimit1_pr = int(np.percentile(medianArray, 1))
            bwLimit10_pr = int(np.percentile(medianArray, 10))
            bwLimit25_pr = int(np.percentile(medianArray, 25))
            bwLimit50_pr = int(np.percentile(medianArray, 50))
            bwLimit75_pr = int(np.percentile(medianArray, 75))
            bwLimit90_pr = int(np.percentile(medianArray, 90))
            bwLimit99_pr = int(np.percentile(medianArray, 99))

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
            "monitorCount":monitorCount,\
            "telemetryCount":telemetryCount,\
            "BPSMax":BPSMax,\
            "BPSMedian":BPSMedian,\
            "BPSp75":BPSp75,\
            "CPSMax":CPSMax,\
            "CPSMedian":CPSMedian,\
            "CPSp75":CPSp75,\
            "bwLimit1":bwLimit1,\
            "bwLimit10":bwLimit10,\
            "bwLimit25":bwLimit25,\
            "bwLimit50":bwLimit50,\
            "bwLimit75":bwLimit75,\
            "bwLimit90":bwLimit90,\
            "bwLimit99":bwLimit99,\
                            
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
            "monitorCount_pr":monitorCount_pr,\
            "telemetryCount_pr":telemetryCount_pr,\
            "BPSMax_pr":BPSMax_pr,\
            "BPSMedian_pr":BPSMedian_pr,\
            "BPSp75_pr":BPSp75_pr,\
            "CPSMax_pr":CPSMax_pr,\
            "CPSMedian_pr":CPSMedian_pr,\
            "CPSp75_pr":CPSp75_pr,\
            "bwLimit1_pr":bwLimit1_pr,\
            "bwLimit10_pr":bwLimit10_pr,\
            "bwLimit25_pr":bwLimit25_pr,\
            "bwLimit50_pr":bwLimit50_pr,\
            "bwLimit75_pr":bwLimit75_pr,\
            "bwLimit90_pr":bwLimit90_pr,\
            "bwLimit99_pr":bwLimit99_pr,\
            #PR ONLY END
            "pLatestVersionStat":pLatestVersionStat,\
            "pTypesStat":pTypesStat,\
            "pStakeTotalStat":pStakeTotalStat,\
            "pStakeRequiredStat":pStakeRequiredStat,\
            "pStakeLatestVersionStat":pStakeLatestVersionStat,\
            "pStakeOnline":latestOnlineWeight,\
            "lastUpdated":str(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),\
            "lastUpdatedUnix":str(time.time()),\
            "speedTest":str(round(medianNormal(speedtest_latest_ms))),\
            }

        #save to global vars used for pushing to blockchain later
        latestGlobalBlocks.append({"time":time.time(), "data": statData['cementedMedian_pr']})
        latestGlobalPeers.append({"time":time.time(), "data": statData['peersMedian_pr']})
        latestGlobalDifficulty.append({"time":time.time(), "data": statData['multiplierMedian_pr']})

    except Exception as e:
        log.error(timeLog('Could not create stat data. Error: %r' %e))
        pass

    try:
        if blockCountMedian > 0 and blockCountMax > 0 and statData is not None and supportedReps is not None and telemetryReps is not None:
            try:
                with open(statFile, 'w') as outfile:
                    outfile.write(simplejson.dumps(statData, indent=2))
            except Exception as e:
                log.error(timeLog('Could not write stat data. Error: %r' %e))

            try:
                #combine monitor list with telemetry list
                combinedList = supportedReps + telemetryReps
                with open(monitorFile, 'w') as outfile:
                    outfile.write(simplejson.dumps(combinedList, indent=2))
            except Exception as e:
                log.error(timeLog('Could not write monitor data. Error: %r' %e))

    except Exception as e:
        log.error(timeLog('Could not write output data. Error: %r' %e))
        pass

async def getPeers():
    global reps
    global pLatestVersionStat
    global pTypesStat
    global pStakeTotalStat
    global pStakeRequiredStat
    global pStakeLatestVersionStat
    global latestOnlineWeight
    global aliases
    global monitorIPExistArray

    while 1:
        startTime = time.time() #to measure the loop speed
        pPeers = []
        pVersions = []
        pStakeTot = 0
        pStakeReq = 0
        supply = 133248061996216572282917317807824970865

        #log.info(timeLog("Verifying peers"))
        monitorPaths = repsInit.copy()
        monitorIPPaths = {'ip':{}}
        monitorIPExistArray = {'ip':{}}

        #Grab connected peer IPs from the node
        params = {
            "action": "peers",
            "peer_details": True,
        }

        try:
            resp = await getRegularRPC(params)
            if 'peers' in resp[0]:
                peers = resp[0]['peers']
                for ipv6,value in peers.items():
                    if ipv6 == '':
                        continue
                    if '[::ffff:' in ipv6: #ipv4
                        ip = re.search('ffff:(.*)\]:', ipv6).group(1)
                    else: #ipv6
                        ip = '[' + re.search('\[(.*)\]:', ipv6).group(1) +']'

                    if ip != "":
                        #Only try to find more monitors from peer IP in main network
                        if not BETA:
                            #Combine with previous list and ignore duplicates
                            exists = False
                            for url in monitorPaths:
                                path = 'http://'+ip
                                if path == url:
                                    exists = True
                                    break
                            if not exists:
                                monitorPaths.append(path)
                                monitorIPPaths[ip] = path

                            exists = False
                            for url in monitorPaths:
                                path = 'http://'+ip+'/nano'
                                if path == url:
                                    exists = True
                                    break
                            if not exists:
                                monitorPaths.append(path)
                                monitorIPPaths[ip] = path

                            exists = False
                            for url in monitorPaths:
                                path = 'http://'+ip+'/nanoNodeMonitor'
                                if path == url:
                                    exists = True
                                    break
                            if not exists:
                                monitorPaths.append(path)
                                monitorIPPaths[ip] = path

                            exists = False
                            for url in monitorPaths:
                                path = 'http://'+ip+'/monitor'
                                if path == url:
                                    exists = True
                                    break
                            if not exists:
                                monitorPaths.append(path)
                                monitorIPPaths[ip] = path

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
            resp = await getRegularRPC(params)
            if 'peers_stake_total' in resp[0] and 'quorum_delta' in resp[0] and 'online_stake_total' in resp[0]:
                pStakeTot = resp[0]['peers_stake_total']
                pStakeReq = resp[0]['quorum_delta']
                latestOnlineWeight = int(resp[0]['online_stake_total']) / int(1000000000000000000000000000000) #used for calculating PR status

                #Find matching IP and include weight in original peer list
                for peer in resp[0]['peers']:
                    for i,cPeer in enumerate(pPeers):
                        if peer['ip'] == cPeer['ip'] and peer['ip'] != '':
                            # append the relevant PR stats here as well
                            weight = int(peer['weight']) / int(1000000000000000000000000000000)

                            pPeers[i] = dict(cPeer, **{"weight": weight}) #update previous vaule
                            continue

        except Exception as e:
            log.warning(timeLog("Could not read quorum from node RPC. %r" %e))
            pass

        #Grab supply
        params = {
            "action": "available_supply"
        }
        try:
            resp = await getRegularRPC(params)
            if 'available' in resp[0]:
                tempSupply = resp[0]['available']
                if int(tempSupply) > 0: #To ensure no devision by zero
                    supply = tempSupply

        except Exception as e:
            log.warning(timeLog("Could not read supply from node RPC. %r" %e))
            pass

        #PERCENTAGE STATS
        try:
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
            combinedTotalWeight = 0
            TCPInLatestCounter = 0
            for peer in pPeers:
                combinedTotalWeight = combinedTotalWeight + (int(peer['weight'])*int(1000000000000000000000000000000))
                if int(peer['version']) == int(maxVersion):
                    combinedWeightInLatest = combinedWeightInLatest + (int(peer['weight'])*int(1000000000000000000000000000000))

                if (peer['type'] == 'tcp'):
                    TCPInLatestCounter += 1

            if (int(pStakeTot) > 0):
                pStakeLatestVersionStat = int(combinedWeightInLatest) / int(combinedTotalWeight) * 100

            if len(pPeers) > 0:
                pTypesStat = TCPInLatestCounter / int(len(pPeers)) * 100
            else:
                pTypesStat = 0

        except Exception as e:
            log.warning(timeLog("Could not calculate weight stat. %r" %e))
            pass

        #Get monitors from Ninja API
        try:
            r = requests.get(ninjaMonitors, timeout=30)
            monitors = r.json()

            if r is not None:
                if len(monitors) > 0:
                    for monitor in monitors:
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
            pass
            #log.warning(timeLog("Could not read monitors from ninja. %r" %e))

        # Get aliases from URL
        if aliasUrl != '':
            try:
                r = requests.get(aliasUrl, timeout=30)
                aliases = r.json()

            except Exception as e:
                pass
                #log.warning(timeLog("Could not read aliases from ninja. %r" %e))

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
                    if path[-4:] != '.htm':
                        tasks.append(asyncio.ensure_future(verifyMonitor('%s/api.php' %path)))
                    else:
                        tasks.append(asyncio.ensure_future(verifyMonitor(path)))

            try:
                with async_timeout.timeout(monitorTimeout):
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
                            # Check if path exist among special IP paths
                            for key in monitorIPPaths:
                                if monitorIPPaths[key] == task.result()[1]:
                                    monitorIPExistArray[key] = {'account':task.result()[0]}
                        repAccounts.append(task.result()[0])

                except Exception as e:
                    pass

                finally:
                    if task.done() and not task.cancelled():
                        task.exception()  # this doesn't raise anything, just mark exception retrieved

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

# publish speed test (change block)
async def publishSpeedTest(source_account, priv_key, rep_account):
    # get info from sending account
    params = {
        'action': 'account_info',
        'account': source_account,
        'count': 1,
        'pending': 'false'
    }
    adjustedbal = '0'

    try:
        # log.info(timeLog("Getting info"))
        resp = requests.post(url=nodeUrl, json=params, timeout=60)
        account_info = resp.json()

        # calculate the state block balance after the send
        adjustedbal = str(int(account_info['balance']))
        # get previous hash
        if 'frontier' in account_info:
            prev = account_info["frontier"]
        else:
            log.error(timeLog("Source account not opened yet"))
            return False

    except Exception as e:
        log.error(timeLog("Could not get block info. %r" %e))
        return False

    work_params = {
        'action': 'work_generate',
        'hash': prev,
        'use_peers': 'true',
        'difficulty': workDiff,
    }

    work = ''
    try:
        #print("Creating work")
        resp = requests.post(url=workUrl, json=work_params, timeout=60)
        work = resp.json()['work']
        if len(work) != 16:
            log.error(timeLog("Could not create work. Bad length."))
            return False

    except Exception as e:
        log.error(timeLog("Could not create work. %r" %e))
        return False

    # create send block
    params = {
        'action': 'block_create',
        'type': 'state',
        'account': source_account,
        'link': '0',
        'balance': adjustedbal,
        'representative': rep_account,
        'previous': prev,
        'key': priv_key,
        'work': work,
    }

    try:
        # log.info(timeLog("Creating block"))
        resp = requests.post(url=nodeUrl, json=params, timeout=120)
        block = resp.json()['block']
        hash = resp.json()['hash']
        if len(hash) != 64:
            log.error(timeLog("Could not create block. %r" %e))
            return False

    except Exception as e:
        log.error(timeLog("Could not create block. %r" %e))
        log.error(resp)
        return False

    # send the transactions
    params = {
        'action': 'process',
        'block': block
    }
    try:
        # log.info(timeLog("Publishing block"))
        resp = requests.post(url=nodeUrl, json=params, timeout=60)
        hash = resp.json()['hash']
        if len(hash) != 64:
            log.error(timeLog("Could not send block. %r" %e))

    except Exception as e:
        log.error(timeLog("Could not send block. %r" %e))
        return False

    return hash

async def speedTest():
    global speedtest_latest
    global speedtest_last_valid
    historyLength = 10

    while True:
        try:
            response = await publishSpeedTest(source_account, priv_key, speedtest_rep)
            if response and len(response) == 64:
                speedtest_latest.append({'hash': response, 'time': int(time.time() * 1000) })
                # Only save historic hashes for 10 x speedTestInterval sec
                if len(speedtest_latest) > historyLength:
                    speedtest_latest.pop(0)

            else:
                log.error(timeLog("Could not speed test. Invalid work"))

            # Check if the last websocket response was too long ago, add 0 to the buffer to indicate timeout
            if time.time() - speedtest_last_valid > float(historyLength * runSpeedTestEvery):
                log.info(timeLog("Speedtest not performed in " + str(time.time() - speedtest_last_valid) + " sec"))
                speedtest_latest_ms.append(0)
                if len(speedtest_latest_ms) > 5:
                    speedtest_latest_ms.pop(0)

            await asyncio.sleep(runSpeedTestEvery)
        except Exception as e:
            log.error(timeLog("Could not speed test. %r" %e))
            await asyncio.sleep(runSpeedTestEvery)

# websocket listener for speed test
async def speedTestWebsocket():
    global speedtest_latest
    global speedtest_latest_ms
    global speedtest_last_valid

    # Predefined subscription message
    msg = {
        "action": "subscribe",
        "topic": "confirmation",
        "options": {
          "accounts": [source_account]
        }
    }
    try:
        async with websockets.connect(speedtest_websocket_1) as websocket:
            await websocket.send(json.dumps(msg))
            while 1:
                rec = json.loads(await websocket.recv())
                # calculate time diff
                duration = 0
                if 'message' in rec:
                    try:
                        for i,test in enumerate(speedtest_latest):
                            if test['hash'] == rec['message']['hash']:
                                speedtest_latest[i]['hash'] = '' # reset so the other websocket doesn't record
                                duration = int(time.time() * 1000) - test['time'] - speedtest_websocket_ping_offset_1
                                speedtest_last_valid = time.time()
                                speedtest_latest_ms.append(duration)
                                if len(speedtest_latest_ms) > 5:
                                    speedtest_latest_ms.pop(0)
                                break
                        log.info(timeLog("Speedtest1: " + str(duration)))
                        

                    except Exception as e:
                        log.error(timeLog("Failed with speed test websocket. %r" %e))

    except Exception as e:
        log.error(timeLog("Websocket connection error"))
        # wait 5sec and reconnect
        await asyncio.sleep(5)
        await speedTestWebsocket()

# websocket listener for speed test backup
async def speedTestWebsocketBackup():
    global speedtest_latest
    global speedtest_latest_ms
    global speedtest_last_valid

    # Predefined subscription message
    msg = {
        "action": "subscribe",
        "topic": "confirmation",
        "options": {
          "accounts": [source_account]
        }
    }
    try:
        async with websockets.connect(speedtest_websocket_2) as websocket:
            await websocket.send(json.dumps(msg))
            while 1:
                rec = json.loads(await websocket.recv())
                # calculate time diff
                duration = 0
                if 'message' in rec:
                    try:
                        for i,test in enumerate(speedtest_latest):
                            if test['hash'] == rec['message']['hash']:
                                speedtest_latest[i]['hash'] = '' # reset so the other websocket doesn't record
                                duration = int(time.time() * 1000) - test['time'] - speedtest_websocket_ping_offset_2
                                speedtest_last_valid = time.time()
                                speedtest_latest_ms.append(duration)
                                if len(speedtest_latest_ms) > 5:
                                    speedtest_latest_ms.pop(0)
                                break
                        log.info(timeLog("Speedtest2: " + str(duration)))
                        

                    except Exception as e:
                        log.error(timeLog("Failed with speed test websocket. %r" %e))

    except Exception as e:
        log.error(timeLog("Websocket connection error"))
        # wait 5sec and reconnect
        await asyncio.sleep(5)
        await speedTestWebsocketBackup()

#Websocket subscription for telemetry
async def websocketLoop():
    global previousMaxBlockCount
    global previousMaxConfirmed
    global previousMedianBlockCount
    global previousMedianConfirmed
    global previousMedianTimeStamp
    global previousMaxBlockCount_pr
    global previousMaxConfirmed_pr
    global previousMedianBlockCount_pr
    global previousMedianConfirmed_pr
    global previousMedianTimeStamp_pr
    global indiPeersPrev
    global websocketCountDownTimer
    global apiShouldCall
    global startTime

    try:
        async with websockets.connect(websocketAddress) as websocket:
            await websocket.send(json.dumps({"action": "subscribe", "topic": "telemetry", "ack": True}))
            ack = json.loads(await websocket.recv())
            if 'ack' in ack:
                if ack['ack'] == 'subscribe':
                    log.info(timeLog("Websocket opened."))
                else:
                    log.warning(timeLog("Could not subscribe to websocket."))
                    return
            else:
                log.warning(timeLog("Could not subscribe to websocket."))
                return

            while 1:
                rec = json.loads(await websocket.recv())
                topic = rec.get("topic", None)
                if topic:
                    metric = rec["message"]
                    if topic == "telemetry":
                        block_count_tele = -1
                        cemented_count_tele = -1
                        unchecked_count_tele = -1
                        account_count_tele = -1
                        bandwidth_cap_tele = -1
                        peer_count_tele = -1
                        protocol_version_number_tele = -1
                        major_version_tele = -1
                        minor_version_tele = -1
                        patch_version_tele = -1
                        pre_release_version_tele = -1
                        uptime_tele = -1
                        timeStamp_tele = time.time()
                        address_tele = -1
                        port_tele = -1

                        if 'block_count' in metric:
                            block_count_tele = int(metric['block_count'])
                        else:
                            continue # failed, do next message
                        if 'timestamp' in metric:
                            timeStamp_tele = int(metric['timestamp'])
                        if 'cemented_count' in metric:
                            cemented_count_tele = int(metric['cemented_count'])
                        if 'unchecked_count' in metric:
                            unchecked_count_tele = int(metric['unchecked_count'])
                        if 'account_count' in metric:
                            account_count_tele = int(metric['account_count'])
                        if 'bandwidth_cap' in metric:
                            bandwidth_cap_tele = metric['bandwidth_cap']
                        if 'peer_count' in metric:
                            peer_count_tele = int(metric['peer_count'])
                        if 'protocol_version' in metric:
                            protocol_version_number_tele = int(metric['protocol_version'])
                        if 'major_version' in metric:
                            major_version_tele = metric['major_version']
                        if 'minor_version' in metric:
                            minor_version_tele = metric['minor_version']
                        if 'patch_version' in metric:
                            patch_version_tele = metric['patch_version']
                        if 'pre_release_version' in metric:
                            pre_release_version_tele = metric['pre_release_version']
                        if 'uptime' in metric:
                            uptime_tele = metric['uptime']
                        if 'address' in metric:
                            address_tele = metric['address']
                        if 'port' in metric:
                            port_tele = metric['port']

                        # calculate individual BPS and CPS
                        BPSPeer = -1
                        CPSPeer = -1
                        previousTimeStamp = deque([0]*checkCPSEvery)

                        if timeStamp_tele != -1 and block_count_tele != -1 and cemented_count_tele != -1 and address_tele != -1 and port_tele != -1:
                            found = False
                            for ip in indiPeersPrev:
                                if ip == address_tele + ':' + port_tele:
                                    found = True
                                    break

                            if not found:
                                # prepare first history data
                                log.info(timeLog("Preparing history for: " + address_tele + ':' + port_tele))

                                timeD = deque([0]*checkCPSEvery)
                                blockD = deque([0]*checkCPSEvery)
                                cementD = deque([0]*checkCPSEvery)

                                timeD.append(timeStamp_tele)
                                timeD.popleft()
                                blockD.append(block_count_tele)
                                blockD.popleft()
                                cementD.append(cemented_count_tele)
                                cementD.popleft()
                                indiPeersPrev[address_tele + ':' + port_tele] = {'timestamp': timeD, 'blockCount': blockD, 'cementCount': cementD,
                                'unchecked_count': unchecked_count_tele, 'peer_count':peer_count_tele, 'protocol_version':protocol_version_number_tele,
                                'account_count':account_count_tele, 'bandwidth_cap':bandwidth_cap_tele, 'uptime':uptime_tele,
                                'major_version':major_version_tele, 'minor_version':minor_version_tele, 'patch_version':patch_version_tele, 'pre_release_version':pre_release_version_tele,
                                'address':address_tele, 'port':port_tele, 'timestamp_local': time.time()}

                            # peer exist in the history, now we can calculate BPS and CPS
                            else:
                                previousMax = indiPeersPrev[address_tele + ':' + port_tele]['blockCount']
                                previousCemented = indiPeersPrev[address_tele + ':' + port_tele]['cementCount']
                                previousTimeStamp = indiPeersPrev[address_tele + ':' + port_tele]['timestamp']

                                # skip updating if the timestamp has not changed, ie. the telemetry data has not changed
                                if timeStamp_tele == previousTimeStamp[0]:
                                    continue

                                if block_count_tele > 0 and previousMax[0] > 0 and (timeStamp_tele - previousTimeStamp[0]) > 0 and previousTimeStamp[0] > 0:
                                    BPSPeer = (block_count_tele - previousMax[0]) / (timeStamp_tele - previousTimeStamp[0])

                                if cemented_count_tele > 0 and previousCemented[0] > 0 and (timeStamp_tele - previousTimeStamp[0]) > 0 and previousTimeStamp[0] > 0:
                                    CPSPeer = (cemented_count_tele - previousCemented[0]) / (timeStamp_tele - previousTimeStamp[0])

                                timeD = indiPeersPrev[ip]['timestamp']
                                timeD.append(timeStamp_tele)
                                timeD.popleft()

                                blockD = indiPeersPrev[ip]['blockCount']
                                blockD.append(block_count_tele)
                                blockD.popleft()

                                cementD = indiPeersPrev[ip]['cementCount']
                                cementD.append(cemented_count_tele)
                                cementD.popleft()

                                # ms to sec (if reported in ms)
                                if timeStamp_tele > 9999999999 and previousTimeStamp[0] > 9999999999 and BPSPeer != -1:
                                    BPSPeer = BPSPeer * 1000
                                    CPSPeer = CPSPeer * 1000

                                indiPeersPrev[ip] = {'timestamp': timeD, 'blockCount': blockD, 'cementCount': cementD,
                                'unchecked_count': unchecked_count_tele, 'peer_count':peer_count_tele, 'protocol_version':protocol_version_number_tele,
                                'account_count':account_count_tele, 'bandwidth_cap':bandwidth_cap_tele, 'uptime':uptime_tele,
                                'major_version':major_version_tele, 'minor_version':minor_version_tele, 'patch_version':patch_version_tele, 'pre_release_version':pre_release_version_tele,
                                'address':address_tele, 'port':port_tele, 'bps':BPSPeer, 'cps':CPSPeer, 'timestamp_local': time.time()}

                                # call the rest of the API calls
                                websocketCountDownTimer = time.time()
                                apiShouldCall = True
                                startTime = time.time()

    except websockets.ConnectionClosed as e:
        log.warning(timeLog("Websocket connection to %s was closed" %websocketAddress))
        await asyncio.sleep(10)
        log.info(timeLog("Reconnecting to %s" %websocketAddress))
        # try reconnect
        await websocketLoop()

    except Exception as e:
        log.warning(timeLog("Failed to process websocket telemetry. %r. Websocket reconnection attempt in 60sec" %e))
        await asyncio.sleep(60)
        # try reconnect
        await websocketLoop()

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

if BETA or DEV:
    futures = [getPeers(), websocketLoop(), websocketCountDown()]
else:
    if speedtest_websocket_2 != '':
        futures = [getPeers(), websocketLoop(), websocketCountDown(), speedTest(), speedTestWebsocket(), speedTestWebsocketBackup()]
    else:
        futures = [getPeers(), websocketLoop(), websocketCountDown(), speedTest(), speedTestWebsocket()]
#futures = [getAPI()]
#futures = [getPeers()]
log.info(timeLog("Starting script"))

try:
    loop.run_until_complete(asyncio.wait(futures))
    #asyncio.run(getPeers(), debug=True)
except KeyboardInterrupt:
    pass
