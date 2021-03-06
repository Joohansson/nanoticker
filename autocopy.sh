
#!/bin/bash
# Copy source files to netdata directories
echo "Copy plugin"
cp netdata/repstats_v21.chart.py /usr/libexec/netdata/python.d/
cp netdata/repstats-b.chart.py /usr/libexec/netdata/python.d/

echo "Copy plugin configs"
cp netdata/repstats_v21.conf /usr/lib/netdata/conf.d/python.d
cp netdata/repstats_v21.conf /etc/netdata/python.d/
cp netdata/repstats-b.conf /usr/lib/netdata/conf.d/python.d
cp netdata/repstats-b.conf /etc/netdata/python.d/

echo "Copy custom dashboard js"
cp netdata/dashboard_custom.js /usr/share/netdata/web/

echo "Copy custom themes"
cp netdata/css/bootstrap-darkest.css //usr/share/netdata/web/css/
cp netdata/css/bootstrap-darkly.css //usr/share/netdata/web/css/
cp netdata/css/dashboard.darkest.css //usr/share/netdata/web/css/
cp netdata/css/dashboard.darkly.css //usr/share/netdata/web/css/

echo "Create folders in var/www and copy dashboard main page"
mkdir -p /var/www/repstat/
mkdir -p /var/www/repstat-beta/
cp -R public_html/ /var/www/repstat/public_html
cp -R public_html/ /var/www/repstat-beta/public_html
rm /var/www/repstat-beta/public_html/index.html
mv /var/www/repstat-beta/public_html/index_beta.html /var/www/repstat-beta/public_html/index.html

echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/

echo "Set www rights"
chown -R www-data:www-data /var/www/repstat/
chown -R www-data:www-data /var/www/repstat-beta/

echo "Set write permission for json files (to allow calc-reps.py to be run locally)"
chmod -R o+w /var/www/repstat/public_html/json
chmod -R o+w /var/www/repstat-beta/public_html/json
