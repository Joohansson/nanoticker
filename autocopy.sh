
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
cp public_html/index.html /var/www/repstats/

echo "Copy dashboard help files"
cp -R public_html/css /var/www/repstats/
cp -R public_html/scss /var/www/repstats/
cp -R public_html/font /var/www/repstats/
cp -R public_html/img /var/www/repstats/
cp -R public_html/js /var/www/repstats/
cp -R public_html/json /var/www/repstats/

echo "Copy icon files"
cp public_html/android-chrome-192x192.png /var/www/repstats/
cp public_html/android-chrome-512x512.png /var/www/repstats/
cp public_html/apple-touch-icon.png /var/www/repstats/
cp public_html/browserconfig.xml /var/www/repstats/
cp public_html/favicon-16x16.png /var/www/repstats/
cp public_html/favicon-32x32.png /var/www/repstats/
cp public_html/favicon.ico /var/www/repstats/
cp public_html/mstile-70x70.png /var/www/repstats/
cp public_html/mstile-144x144.png /var/www/repstats/
cp public_html/mstile-150x150.png /var/www/repstats/
cp public_html/mstile-310x150.png /var/www/repstats/
cp public_html/mstile-310x310.png /var/www/repstats/
cp public_html/safari-pinned-tab.svg /var/www/repstats/
cp public_html/site.webmanifest /var/www/repstats/

echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/

echo "Set write permission for json files (to allow calc-reps.py to be run locally)"
chmod -R o+w /var/www/repstats/json
