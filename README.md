
# Nano Ticker

A real-time statistical tool to check Nano network health. Using data from public Nano Node Monitors.

[Public Site](https://nanoticker.info)

## Install
bash <(curl -Ss https://my-netdata.io/kickstart.sh) --no-updates
chmod +x autocopy.sh
./autocopy.sh

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

## Developer instructions


Find this useful? Send me a Nano donation at `nano_1gur37mt5cawjg5844bmpg8upo4hbgnbbuwcerdobqoeny4ewoqshowfakfo`
