# -*- coding: utf-8 -*-
# Description: RepStats netdata python.d module
# Author: Joohansson
# SPDX-License-Identifier: GPL-3.0-or-later
# Updated: 2019-08-12

from bases.FrameworkServices.UrlService import UrlService
import json
from collections import deque #for array shifting

# default module values (can be overridden per job in `config`)
update_every = 15 #update chart every 15 second (changing this will change TPS Ave interval to interval*40 sec)
priority = 1000 #where it will appear on the main stat page and menu (60000 will place it last)
#retries = 60

# default job configuration (overridden by python.d.plugin)
# config = {'local': {
#             'update_every': update_every,
#             'retries': retries,
#             'priority': priority,
#             'url': 'http://localhost/stats.json'
#          }}

# charts order (can be overridden if you want less charts, or different order)

ORDER = ['block_count_max', 'block_count_median', 'unchecked', 'peers', 'tps_max', 'tps_median',\
'confirmations', 'block_diff', 'multiplier', 'api_time', 'supported', 'peerstat',\
'block_count_max_pr', 'block_count_median_pr', 'unchecked_pr', 'peers_pr', 'tps_max_pr', 'tps_median_pr',\
'confirmations_pr', 'block_diff_pr', 'multiplier_pr', 'api_time_pr', 'supported_pr']

CHARTS = {
    'block_count_max': {
        'options': [None, 'Blocks Max', 'blocks', 'Checked Blocks','reps.blocks', 'area'],
        'lines': [
            ["saved_blocks_max", "checked", None, 'absolute'],
            ["confirmed_max", "conf", None, 'absolute']
        ]
    },
    'block_count_median': {
        'options': [None, 'Blocks Median', 'blocks', 'Checked Blocks','reps.blocks', 'area'],
        'lines': [
            ["saved_blocks_median", "checked", None, 'absolute'],
            ["confirmed_median", "conf", None, 'absolute']
        ]
    },
    'unchecked': {
        'options': [None, 'Unchecked', 'blocks', 'Unchecked Blocks','reps.unchecked', 'line'],
        'lines': [
            ["unchecked_max", "max", None, 'absolute'],
            ["unchecked_median", "median", None, 'absolute'],
            ["unchecked_min", "min", None, 'absolute']
        ]
    },
    'peers': {
        'options': [None, 'Peers', 'peers', 'Peers','reps.peers', 'line'],
        'lines': [
            ["peers_max", "max", None, 'absolute'],
            ["peers_median", "median", None, 'absolute'],
            ["peers_min", "min", None, 'absolute']
        ]
    },
    'tps_max': {
        'options': [None, 'TPS Max', 'tx/s', 'TPS 10 min','reps.tps', 'line'],
        'lines': [
            ["bps_max_10", None, 'absolute', 1, 1000],
            ["cps_max_10", None, 'absolute', 1, 1000]
        ]
    },
    'tps_median': {
        'options': [None, 'TPS Median', 'tx/s', 'TPS 10 min','reps.tps', 'line'],
        'lines': [
            ["bps_median_10", None, 'absolute', 1, 1000],
            ["cps_median_10", None, 'absolute', 1, 1000]
        ]
    },
    'confirmations': {
        'options': [None, 'Confirmation Time', 'ms', 'Conf-Time Max 5min/2048tx','reps.conf', 'line'],
        'lines': [
            ["average_min", "ave min", None, 'absolute'],
            ["average_median", "average", None, 'absolute'],
            ["perc_50", "perc 50", None, 'absolute'],
            #["perc_75", "perc 75", None, 'absolute'],
            ["perc_90", "perc 90", None, 'absolute'],
            #["perc_95", "perc 95", None, 'absolute'],
            ["perc_99", "perc 99", None, 'absolute']
        ]
    },
    'block_diff': {
        'options': [None, 'Block Diff', 'blocks', 'Block Diff','reps.diff', 'line'],
        'lines': [
            ["diff_max", None, 'absolute'],
            ["diff_median", None, 'absolute']

        ]
    },
    'multiplier': {
        'options': [None, 'Difficulty', 'multiplier', 'Difficulty','reps.multiplier', 'line'],
        'lines': [
            ["multi_max", None, 'absolute',1,1000],
            ["multi_median", None, 'absolute',1,1000],
            ["multi_min", None, 'absolute',1,1000]
        ]
    },
    'api_time': {
        'options': [None, 'API Time', 'ms', 'API processing time','reps.api', 'line'],
        'lines': [
            ["api_max", "max", None, 'absolute'],
            ["api_median", "median", None, 'absolute'],
            ["api_min", "min", None, 'absolute']
        ]
    },
    'supported': {
        'options': [None, 'Supported', 'monitors', 'NodeMonitors Support','reps.supported', 'line'],
        'lines': [
            ["supported_blocks", "block count", None, 'absolute'],
            ["supported_cemented", "cemented", None, 'absolute'],
            ["supported_peers", "peers", None, 'absolute'],
            ["supported_conf", "conf times", None, 'absolute'],
            ["supported_proc", "proc time", None, 'absolute'],
            ["supported_multiplier", "multiplier", None, 'absolute']
        ]
    },
    'peerstat': {
        'options': [None, 'Peers & Stake', '%', 'Protocol and weight from connected nodes','reps.peerstat', 'line'],
        'lines': [
            ["latest_version", None, 'absolute',1,1000],
            ["tcp", None, 'absolute',1,1000],
            ["stake_req", None, 'absolute',1,1000],
            ["stake_latest", None, 'absolute',1,1000],
            ["stake_tot", None, 'absolute',1,1000]
        ]
    },
    #PR ONLY
    'block_count_max_pr': {
        'options': [None, 'Blocks Max', 'blocks', 'Checked Blocks','reps.blocks', 'area'],
        'lines': [
            ["saved_blocks_max_pr", "checked", None, 'absolute'],
            ["confirmed_max_pr", "conf", None, 'absolute']
        ]
    },
    'block_count_median_pr': {
        'options': [None, 'Blocks Median', 'blocks', 'Checked Blocks','reps.blocks', 'area'],
        'lines': [
            ["saved_blocks_median_pr", "checked", None, 'absolute'],
            ["confirmed_median_pr", "conf", None, 'absolute']
        ]
    },
    'unchecked_pr': {
        'options': [None, 'Unchecked', 'blocks', 'Unchecked Blocks','reps.unchecked', 'line'],
        'lines': [
            ["unchecked_max_pr", "max", None, 'absolute'],
            ["unchecked_median_pr", "median", None, 'absolute'],
            ["unchecked_min_pr", "min", None, 'absolute']
        ]
    },
    'peers_pr': {
        'options': [None, 'Peers', 'peers', 'Peers','reps.peers', 'line'],
        'lines': [
            ["peers_max_pr", "max", None, 'absolute'],
            ["peers_median_pr", "median", None, 'absolute'],
            ["peers_min_pr", "min", None, 'absolute']
        ]
    },
    'tps_max_pr': {
        'options': [None, 'TPS Max', 'tx/s', 'TPS 10 min','reps.tps', 'line'],
        'lines': [
            ["bps_max_10_pr", None, 'absolute', 1, 1000],
            ["cps_max_10_pr", None, 'absolute', 1, 1000]
        ]
    },
    'tps_median_pr': {
        'options': [None, 'TPS Median', 'tx/s', 'TPS 10 min','reps.tps', 'line'],
        'lines': [
            ["bps_median_10_pr", None, 'absolute', 1, 1000],
            ["cps_median_10_pr", None, 'absolute', 1, 1000]
        ]
    },
    'confirmations_pr': {
        'options': [None, 'Confirmation Time', 'ms', 'Conf-Time Max 5min/2048tx','reps.conf', 'line'],
        'lines': [
            ["average_min_pr", "ave min", None, 'absolute'],
            ["average_median_pr", "average", None, 'absolute'],
            ["perc_50_pr", "perc 50", None, 'absolute'],
            #["perc_75_pr", "perc 75", None, 'absolute'],
            ["perc_90_pr", "perc 90", None, 'absolute'],
            #["perc_95_pr", "perc 95", None, 'absolute'],
            ["perc_99_pr", "perc 99", None, 'absolute']
        ]
    },
    'block_diff_pr': {
        'options': [None, 'Block Diff', 'blocks', 'Block Diff','reps.diff', 'line'],
        'lines': [
            ["diff_max_pr", None, 'absolute'],
            ["diff_median_pr", None, 'absolute']

        ]
    },
    'multiplier_pr': {
        'options': [None, 'difficulty', 'multiplier', 'Difficulty','reps.multiplier', 'line'],
        'lines': [
            ["multi_max_pr", None, 'absolute',1,1000],
            ["multi_median_pr", None, 'absolute',1,1000],
            ["multi_min_pr", None, 'absolute',1,1000]
        ]
    },
    'api_time_pr': {
        'options': [None, 'API Time', 'ms', 'API processing time','reps.api', 'line'],
        'lines': [
            ["api_max_pr", "max", None, 'absolute'],
            ["api_median_pr", "median", None, 'absolute'],
            ["api_min_pr", "min", None, 'absolute']
        ]
    },
    'supported_pr': {
        'options': [None, 'Supported', 'monitors', 'NodeMonitors Support','reps.supported', 'line'],
        'lines': [
            ["supported_blocks_pr", "block count", None, 'absolute'],
            ["supported_cemented_pr", "cemented", None, 'absolute'],
            ["supported_peers_pr", "peers", None, 'absolute'],
            ["supported_conf_pr", "conf times", None, 'absolute'],
            ["supported_proc_pr", "proc time", None, 'absolute'],
            ["supported_multiplier_pr", "multiplier", None, 'absolute']
        ]
    },
}

class Service(UrlService):
    def __init__(self, configuration=None, name=None):
        UrlService.__init__(self, configuration=configuration, name=name)
        self.url = self.configuration.get('url', 'https://b-monitor.repnode.org/stats-beta.json')
        self.order = ORDER
        self.definitions = CHARTS
        self.blocks_max_old = 0 #block count previous poll
        self.blocks_median_old = 0 #block count previous poll
        self.bps_max_old = deque([0]*8) #tps history last 8 polls, init with 8 zeroes
        self.bps_median_old = deque([0]*8) #tps history last 8 polls, init with 8 zeroes
        self.cemented_max_old = 0 #cemented count previous poll
        self.cemented_median_old = 0 #cemented count previous poll
        self.cps_max_old = deque([0]*8) #cps history last 8 polls, init with 8 zeroes
        self.cps_median_old = deque([0]*8) #cps history last 8 polls, init with 8 zeroes

        #PR ONLY
        self.blocks_max_old_pr = 0 #block count previous poll
        self.blocks_median_old_pr = 0 #block count previous poll
        self.bps_max_old_pr = deque([0]*8) #tps history last 8 polls, init with 8 zeroes
        self.bps_median_old_pr = deque([0]*8) #tps history last 8 polls, init with 8 zeroes
        self.cemented_max_old_pr = 0 #cemented count previous poll
        self.cemented_median_old_pr = 0 #cemented count previous poll
        self.cps_max_old_pr = deque([0]*8) #cps history last 8 polls, init with 8 zeroes
        self.cps_median_old_pr = deque([0]*8) #cps history last 8 polls, init with 8 zeroes

    def _get_data(self):
        """
        Format data received from http request
        :return: dict
        """

        #Convert raw api data to json
        try:
            raw = self._get_raw_data()
            parsed = json.loads(raw)
        except AttributeError:
            return None

        #Keys to read from api data with the first entry is keys used by the charts
        apiKeys = [('saved_blocks_max','blockCountMax',int,1), ('saved_blocks_median','blockCountMedian',int,1), ('confirmed_max','cementedMax',int,1), ('confirmed_median','cementedMedian',int,1),
            ('unchecked_max','uncheckedMax',int,1),('unchecked_median','uncheckedMedian',int,1),('unchecked_min','uncheckedMin',int,1),('peers_max','peersMax',int,1),
            ('peers_median','peersMedian',int,1),('peers_min','peersMin',int,1),('average_median','confAveMedian',int,1),('average_min','confAveMin',int,1),('perc_50','conf50Median',int,1),
            ('perc_75','conf75Median',int,1),('perc_90','conf90Median',int,1),('perc_99','conf99Median',int,1),('diff_median','diffMedian',int,1),
            ('diff_max','diffMax',int,1),('multi_max','multiplierMax',float,1000),('multi_median','multiplierMedian',float,1000),('multi_min','multiplierMin',float,1000),
            ('api_max','procTimeMax',int,1),('api_median','procTimeMedian',int,1),('api_min','procTimeMin',int,1),
            ('supported_blocks','lenBlockCount',int,1),('supported_cemented','lenCemented',int,1),('supported_peers','lenPeers',int,1),
            ('supported_conf','lenConf50',int,1),('supported_proc','lenProcTime',int,1),('supported_multiplier','lenMultiplier',int,1),
            ('latest_version','pLatestVersionStat',float,1000),('tcp','pTypesStat',float,1000),('stake_tot','pStakeTotalStat',float,1000),
            ('stake_req','pStakeRequiredStat',float,1000),('stake_latest','pStakeLatestVersionStat',float,1000)]

        apiKeys_pr = [('saved_blocks_max_pr','blockCountMax_pr',int,1), ('saved_blocks_median_pr','blockCountMedian_pr',int,1), ('confirmed_max_pr','cementedMax_pr',int,1), ('confirmed_median_pr','cementedMedian_pr',int,1),
            ('unchecked_max_pr','uncheckedMax_pr',int,1),('unchecked_median_pr','uncheckedMedian_pr',int,1),('unchecked_min_pr','uncheckedMin_pr',int,1),('peers_max_pr','peersMax_pr',int,1),
            ('peers_median_pr','peersMedian_pr',int,1),('peers_min_pr','peersMin_pr',int,1),('average_median_pr','confAveMedian_pr',int,1),('average_min_pr','confAveMin_pr',int,1),('perc_50_pr','conf50Median_pr',int,1),
            ('perc_75_pr','conf75Median_pr',int,1),('perc_90_pr','conf90Median_pr',int,1),('perc_99_pr','conf99Median_pr',int,1),('diff_median_pr','diffMedian_pr',int,1),
            ('diff_max_pr','diffMax_pr',int,1),('multi_max_pr','multiplierMax_pr',float,1000),('multi_median_pr','multiplierMedian_pr',float,1000),('multi_min_pr','multiplierMin_pr',float,1000),
            ('api_max_pr','procTimeMax_pr',int,1),('api_median_pr','procTimeMedian_pr',int,1),('api_min_pr','procTimeMin_pr',int,1),
            ('supported_blocks_pr','lenBlockCount_pr',int,1),('supported_cemented_pr','lenCemented_pr',int,1),('supported_peers_pr','lenPeers_pr',int,1),
            ('supported_conf_pr','lenConf50_pr',int,1),('supported_proc_pr','lenProcTime_pr',int,1),('supported_multiplier_pr','lenMultiplier_pr',int,1),
            ('latest_version','pLatestVersionStat',float,1000),('tcp','pTypesStat',float,1000),('stake_tot','pStakeTotalStat',float,1000),
            ('stake_req','pStakeRequiredStat',float,1000),('stake_latest','pStakeLatestVersionStat',float,1000)]

        r = dict()

        #Extract data from json based on repstat keys
        for new_key, orig_key, keytype, mul in apiKeys:
            try:
                r[new_key] = keytype(mul * parsed[orig_key]) #for example multiply by 1000 here
            except Exception:
                r[new_key] = 0 #replace with 0 if value missing from API
                continue

        #PR ONLY
        for new_key, orig_key, keytype, mul in apiKeys_pr:
            try:
                r[new_key] = keytype(mul * parsed[orig_key]) #for example multiply by 1000 here
            except Exception:
                r[new_key] = 0 #replace with 0 if value missing from API
                continue

        if (self.blocks_max_old == 0):
            self.blocks_max_old = r['saved_blocks_max'] #Initialize with block count first time to not get large tps before running one iteration
        r['bps_max'] = 1000 * (r['saved_blocks_max']-self.blocks_max_old) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.blocks_max_old = r['saved_blocks_max'] #update for next iteration
        self.bps_max_old.append(r['bps_max'])
        self.bps_max_old.popleft()

        #Calculate bps past X iterations based on average bps
        sum = 0
        for bps in self.bps_max_old:
            sum = sum + bps
        r['bps_max_10'] = sum / len(self.bps_max_old)

        #Calculate bps median based on previous block read
        if (self.blocks_median_old == 0):
            self.blocks_median_old = r['saved_blocks_median'] #Initialize with block count first time to not get large tps before running one iteration
        r['bps_median'] = 1000 * (r['saved_blocks_median']-self.blocks_median_old) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.blocks_median_old = r['saved_blocks_median'] #update for next iteration
        self.bps_median_old.append(r['bps_median'])
        self.bps_median_old.popleft()

        #Calculate bps past X iterations based on average bps
        sum = 0
        for bps in self.bps_median_old:
            sum = sum + bps
        r['bps_median_10'] = sum / len(self.bps_median_old)

        #Calculate cps max based on previous block read
        if (self.cemented_max_old == 0):
            self.cemented_max_old = r['confirmed_max'] #Initialize with block count first time to not get large tps before running one iteration
        r['cps_max'] = 1000 * (r['confirmed_max']-self.cemented_max_old) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.cemented_max_old = r['confirmed_max'] #update for next iteration
        self.cps_max_old.append(r['cps_max'])
        self.cps_max_old.popleft()

        #Calculate cps past X iterations based on average bps
        sum = 0
        for cps in self.cps_max_old:
            sum = sum + cps
        r['cps_max_10'] = sum / len(self.cps_max_old)

        #Calculate cps median based on previous block read
        if (self.cemented_median_old == 0):
            self.cemented_median_old = r['confirmed_median'] #Initialize with block count first time to not get large tps before running one iteration
        r['cps_median'] = 1000 * (r['confirmed_median']-self.cemented_median_old) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.cemented_median_old = r['confirmed_median'] #update for next iteration
        self.cps_median_old.append(r['cps_median'])
        self.cps_median_old.popleft()

        #Calculate cps past X iterations based on average bps
        sum = 0
        for cps in self.cps_median_old:
            sum = sum + cps
        r['cps_median_10'] = sum / len(self.cps_median_old)

        #----------PR ONLY--------
        #Calculate bps max based on previous block read
        if (self.blocks_max_old_pr == 0):
            self.blocks_max_old_pr = r['saved_blocks_max_pr'] #Initialize with block count first time to not get large tps before running one iteration
        r['bps_max_pr'] = 1000 * (r['saved_blocks_max_pr']-self.blocks_max_old_pr) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.blocks_max_old_pr = r['saved_blocks_max_pr'] #update for next iteration
        self.bps_max_old_pr.append(r['bps_max_pr'])
        self.bps_max_old_pr.popleft()

        #Calculate bps past X iterations based on average bps
        sum = 0
        for bps in self.bps_max_old_pr:
            sum = sum + bps
        r['bps_max_10_pr'] = sum / len(self.bps_max_old_pr)

        #Calculate bps median based on previous block read
        if (self.blocks_median_old_pr == 0):
            self.blocks_median_old_pr = r['saved_blocks_median_pr'] #Initialize with block count first time to not get large tps before running one iteration
        r['bps_median_pr'] = 1000 * (r['saved_blocks_median_pr']-self.blocks_median_old_pr) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.blocks_median_old_pr = r['saved_blocks_median_pr'] #update for next iteration
        self.bps_median_old_pr.append(r['bps_median_pr'])
        self.bps_median_old_pr.popleft()

        #Calculate bps past X iterations based on average bps
        sum = 0
        for bps in self.bps_median_old_pr:
            sum = sum + bps
        r['bps_median_10_pr'] = sum / len(self.bps_median_old_pr)

        #Calculate cps max based on previous block read
        if (self.cemented_max_old_pr == 0):
            self.cemented_max_old_pr = r['confirmed_max_pr'] #Initialize with block count first time to not get large tps before running one iteration
        r['cps_max_pr'] = 1000 * (r['confirmed_max_pr']-self.cemented_max_old_pr) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.cemented_max_old_pr = r['confirmed_max_pr'] #update for next iteration
        self.cps_max_old_pr.append(r['cps_max_pr'])
        self.cps_max_old_pr.popleft()

        #Calculate cps past X iterations based on average bps
        sum = 0
        for cps in self.cps_max_old_pr:
            sum = sum + cps
        r['cps_max_10_pr'] = sum / len(self.cps_max_old_pr)

        #Calculate cps median based on previous block read
        if (self.cemented_median_old_pr == 0):
            self.cemented_median_old_pr = r['confirmed_median_pr'] #Initialize with block count first time to not get large tps before running one iteration
        r['cps_median_pr'] = 1000 * (r['confirmed_median_pr']-self.cemented_median_old_pr) / update_every #use previous iteration (multiply 1000 and divide with 1000 in chart to get decimals)
        self.cemented_median_old_pr = r['confirmed_median_pr'] #update for next iteration
        self.cps_median_old_pr.append(r['cps_median_pr'])
        self.cps_median_old_pr.popleft()

        #Calculate cps past X iterations based on average bps
        sum = 0
        for cps in self.cps_median_old_pr:
            sum = sum + cps
        r['cps_median_10_pr'] = sum / len(self.cps_median_old_pr)

        return r or None
