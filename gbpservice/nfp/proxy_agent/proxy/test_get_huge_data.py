from gbpservice.nfp.lib import RestClientOverUnix as rcu
import time
import json

while True:
    try:
        s_time = time.time()
        data = json.loads(rcu.get('get_notifications'))
        e_time = time.time()
        print "GET -> s_time [%s] e_time [%s] len [%d]" %(s_time, e_time, len(data))
    except Exception as exc:
        print "GET -> Exception : %s" %(exc)
