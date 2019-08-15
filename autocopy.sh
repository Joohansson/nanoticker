
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
echo "Set netdata read access for dashboard and style"
chown -R netdata:netdata /usr/share/netdata/web/reps.html
chown -R netdata:netdata /usr/share/netdata/web/reps.css
echo "Copy plugin config to user location"
cp repstats.conf /etc/netdata/python.d/
