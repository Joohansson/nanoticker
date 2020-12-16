
# Nano Ticker

A real-time statistical tool to check Nano network health. Using data from public Nano Node Monitors.

[Public Site](https://nanoticker.info)

## Requirements
- Ubuntu 20.04 preferred (18 possible)
- Apache: sudo apt install apache2

## Install

I suggest --no-updates to not accidentially break the plugin. That being said, I cannot guarantee the plugin will work with the latest Netdata at the time you run this.

    bash <(curl -Ss https://my-netdata.io/kickstart.sh) --no-updates --stable-channel
    chmod +x autocopy.sh
    ./autocopy.sh
    service netdata restart

## Instructions and Config
You will run script/calc-reps.py on a machine that has connection to a Nano node. First open it and check the following:

- BETA and DEV: If running on main net, set both to False
- nodeUrl, telemetryAddress, telemetryPort and websocket needs to correspond to your node settings
- statFile and monitorFile must be written by the script to a webserver that can be reached publicly from any remote client browser (cross-origin is a common error)
- localTelemetryAccount is the nano account of your representative (if using that as the rpc/telemetry node). It's handled a bit different.

To run calc-reps.py you need repList.py in the same folder and the following:
- Python: At least 3.6
- Python aiohttp: pip3 install aiohttp
- Python websockets: pip3 install websockets
- Python numpy: pip3 install numpy

The netdata folder contains the python plugin for Netdata. Both for main net and beta net. It's configurable via the .conf files.
The script/repList.py may be outdated but that's just for the initial sync. The peers are updated while the script is running but may take a while.

On the frontend machine (or if you use the same as backend):
- The netdata nanoticker plugin will connect and read the stats.json file on the webserver (repstats_v21.conf)
- The webpage itself (public_html/index.html) will connect and read both stats.json and monitors.json. It's configurable in the html file.
- You may want to turn off google analytics in the index.html file
- The main nanoticker site is hosted at /var/www/repstat/index.html
- The beta nanoticker site is hosted at /var/www/repstat-beta/index.html

## Debug the plugins
grep python /var/log/netdata/error.log

    /usr/libexec/netdata/plugins.d/python.d.plugin repstats debug trace
    /usr/libexec/netdata/plugins.d/python.d.plugin repstats-b debug trace
    /usr/libexec/netdata/plugins.d/python.d.plugin 1 debug repstats
    /usr/libexec/netdata/plugins.d/python.d.plugin 1 debug repstats-b

## Config netdata
nano /etc/netdata/netdata.conf

    hostname = NanoTicker
    history = 100800
    update every = 6
    memory mode = dbengine
    page cache size = 500
    dbengine disk space = 500


Find this useful? Send me a Nano donation at `nano_1gur37mt5cawjg5844bmpg8upo4hbgnbbuwcerdobqoeny4ewoqshowfakfo`
