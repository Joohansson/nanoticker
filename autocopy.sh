
#!/bin/bash
# Copy source files to netdata directories
echo "Copy plugin"
cp repstats.chart.py /usr/libexec/netdata/python.d/

echo "Copy plugin config to default location"
cp repstats.conf /usr/lib/netdata/conf.d/python.d

echo "Copy dashboard"
cp reps.html /usr/share/netdata/web

echo "Copy dashboard style"
cp reps.css /usr/share/netdata/web

echo "Backup original dashboard.js"
mv /usr/share/netdata/web/dashboard.js /usr/share/netdata/web/dashboard.js.bak

echo "Copy custom dashboard bootstrap theme"
cp dashboard.js /usr/share/netdata/web
cp dashboard.darkly /usr/share/netdata/web/
cp bootstrap-darkly.css /usr/share/netdata/web/css

echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/

echo "Set write permission for all users to www and netdata folders"
chmod -R o+w /usr/share/netdata/web/
chmod -R o+w /var/www/

echo "Copy plugin config to user location"
cp repstats.conf /etc/netdata/python.d/
