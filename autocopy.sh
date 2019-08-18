
#!/bin/bash
# Copy source files to netdata directories
echo "Copy plugin"
cp netdata/repstats.chart.py /usr/libexec/netdata/python.d/

echo "Copy plugin configs"
cp netdata/repstats.conf /usr/lib/netdata/conf.d/python.d
cp netdata/repstats.conf /etc/netdata/python.d/

echo "Copy custom dashboard js"
cp netdata/dashboard_custom.js /usr/share/netdata/web/

echo "Copy dashboard main page"
cp -R public_html/ /var/www/repstat/public_html

echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/

echo "Set write permission for json files (to allow calc-reps.py to be run locally)"
chmod -R o+w /var/www/repstat/public_html/json
