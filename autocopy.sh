
#!/bin/bash
# Copy source files to netdata directories
echo "Copy plugin"
cp repstats.chart.py /usr/libexec/netdata/python.d/

echo "Copy plugin config to default location"
cp repstats.conf /usr/lib/netdata/conf.d/python.d

echo "Renaming default index.html to full.html"
mv /usr/share/netdata/web/index.html /usr/share/netdata/web/full.html

echo "Copy dashboard"
cp index.html /usr/share/netdata/web

echo "Copy dashboard style"
cp reps.css /usr/share/netdata/web

echo "Copy custom dashboard"
cp dashboard_custom.js /usr/share/netdata/web/

echo "Copy sample json files"
cp stats.json /usr/share/netdata/web/
cp monitor.json /usr/share/netdata/web/

echo "Copy datatable bootstrap files"
cp -R css /usr/share/netdata/web/
cp -R scss /usr/share/netdata/web/
cp -R font /usr/share/netdata/web/
cp -R img /usr/share/netdata/web/
cp -R js /usr/share/netdata/web/

echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/

echo "Set write permission for all users to netdata folders (to allow calc-reps.py to be run locally)"
chmod -R o+w /usr/share/netdata/web/

echo "Copy plugin config to user location"
cp repstats.conf /etc/netdata/python.d/
