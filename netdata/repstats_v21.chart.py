# -*- coding: utf-8 -*-
# Description: RepStats netdata python.d module
# Author: Joohansson
# SPDX-License-Identifier: GPL-3.0-or-later
# Updated: 2019-08-12

from bases.FrameworkServices.UrlService import UrlService
import json
from collections import deque #for array shifting

# default module values (can be overridden per job in `config`)
update_every = 20 #update chart every x second (changing this will change TPS Ave interval to interval*x sec)
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
            #["supported_proc", "proc time", None, 'absolute'],
            ["supported_multiplier", "difficulty", None, 'absolute']
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
            #["supported_proc_pr", "proc time", None, 'absolute'],
            ["supported_multiplier_pr", "difficulty", None, 'absolute']
        ]
    },
}

class Service(UrlService):
    def __init__(self, configuration=None, name=None):
        UrlService.__init__(self, configuration=configuration, name=name)
        self.url = self.configuration.get('url', 'https://nanoticker.info/json/stats-v21.json')
        self.order = ORDER
        self.definitions = CHARTS

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
            ('stake_req','pStakeRequiredStat',float,1000),('stake_latest','pStakeLatestVersionStat',float,1000),
            ('bps_max_10','BPSMax',float,1000),('bps_median_10','BPSMedian',float,1000),('cps_max_10','CPSMax',float,1000),('cps_median_10','CPSMedian',float,1000)]

        apiKeys_pr = [('saved_blocks_max_pr','blockCountMax_pr',int,1), ('saved_blocks_median_pr','blockCountMedian_pr',int,1), ('confirmed_max_pr','cementedMax_pr',int,1), ('confirmed_median_pr','cementedMedian_pr',int,1),
            ('unchecked_max_pr','uncheckedMax_pr',int,1),('unchecked_median_pr','uncheckedMedian_pr',int,1),('unchecked_min_pr','uncheckedMin_pr',int,1),('peers_max_pr','peersMax_pr',int,1),
            ('peers_median_pr','peersMedian_pr',int,1),('peers_min_pr','peersMin_pr',int,1),('average_median_pr','confAveMedian_pr',int,1),('average_min_pr','confAveMin_pr',int,1),('perc_50_pr','conf50Median_pr',int,1),
            ('perc_75_pr','conf75Median_pr',int,1),('perc_90_pr','conf90Median_pr',int,1),('perc_99_pr','conf99Median_pr',int,1),('diff_median_pr','diffMedian_pr',int,1),
            ('diff_max_pr','diffMax_pr',int,1),('multi_max_pr','multiplierMax_pr',float,1000),('multi_median_pr','multiplierMedian_pr',float,1000),('multi_min_pr','multiplierMin_pr',float,1000),
            ('api_max_pr','procTimeMax_pr',int,1),('api_median_pr','procTimeMedian_pr',int,1),('api_min_pr','procTimeMin_pr',int,1),
            ('supported_blocks_pr','lenBlockCount_pr',int,1),('supported_cemented_pr','lenCemented_pr',int,1),('supported_peers_pr','lenPeers_pr',int,1),
            ('supported_conf_pr','lenConf50_pr',int,1),('supported_proc_pr','lenProcTime_pr',int,1),('supported_multiplier_pr','lenMultiplier_pr',int,1),
            ('latest_version','pLatestVersionStat',float,1000),('tcp','pTypesStat',float,1000),('stake_tot','pStakeTotalStat',float,1000),
            ('stake_req','pStakeRequiredStat',float,1000),('stake_latest','pStakeLatestVersionStat',float,1000),
            ('bps_max_10_pr','BPSMax_pr',float,1000),('bps_median_10_pr','BPSMedian_pr',float,1000),('cps_max_10_pr','CPSMax_pr',float,1000),('cps_median_10_pr','CPSMedian_pr',float,1000)]

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

        return r or None
