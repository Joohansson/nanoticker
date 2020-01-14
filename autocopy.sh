
#!/bin/bash
echo "Set www rights"
chown -R www-data:www-data /var/www/repstat/
chown -R www-data:www-data /var/www/repstat-beta/

# Copy source files to netdata directories
echo "Copy plugin"
cp netdata/repstats.chart.py /usr/libexec/netdata/python.d/
cp netdata/repstats-b.chart.py /usr/libexec/netdata/python.d/

echo "Copy plugin configs"
cp netdata/repstats.conf /usr/lib/netdata/conf.d/python.d
cp netdata/repstats.conf /etc/netdata/python.d/
cp netdata/repstats-b.conf /usr/lib/netdata/conf.d/python.d
cp netdata/repstats-b.conf /etc/netdata/python.d/

echo "Copy custom dashboard js"
cp netdata/dashboard_custom.js /usr/share/netdata/web/

echo "Copy custom themes"
cp netdata/css/bootstrap-darkest.css //usr/share/netdata/web/css/
cp netdata/css/bootstrap-darkly.css //usr/share/netdata/web/css/
cp netdata/css/dashboard.darkest.css //usr/share/netdata/web/css/
cp netdata/css/dashboard.darkly.css //usr/share/netdata/web/css/

echo "Copy dashboard main page"
cp -R public_html/ /var/www/repstat/public_html

echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/

echo "Set write permission for json files (to allow calc-reps.py to be run locally)"
chmod -R o+w /var/www/repstat/public_html/json
