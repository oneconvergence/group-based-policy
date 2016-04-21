from subprocess import call, Popen, PIPE
import json
import sys


class ConfigureIPtables:
	def __init__(self, json_blob):
		ps = Popen(["sysctl", "net.ipv4.ip_forward"], stdout=PIPE)
		output = ps.communicate()[0]
		if "0" in output:
			print "Enabling IP forwarding ..."
			call(["sysctl", "-w", "net.ipv4.ip_forward=1"])
		else:
			print "IP forwarding already enabled"
                try:
		    self.rules_json = json.loads(json_blob)
                except ValueError:
                    sys.exit('Given json_blob is not a valid json')

	def update_chain(self):
		ps = Popen(["iptables", "-L"], stdout=PIPE)
                output = ps.communicate()[0]

                #check if chain is present if not create new chain
                if not "testchain" in output:
                    print "Creating new chain ..."
                    call(["iptables", "-F"])
                    call(["iptables", "-N", "testchain"])
                    call(["iptables", "-t", "filter", "-A", "FORWARD", "-j", "testchain"])
		    call(["iptables", "-A", "FORWARD", "-j", "DROP"])
                
                #flush chain of existing rules
                call(["iptables", "-F", "testchain"])
                #return 

                #Update chain with new rules
                print "Updating chain with new rules ..."
		count = 0
		for rule in self.rules_json.get('rules'):
                	print "adding rule %d" %(count) 
			try:
				name = rule['name']
				action_values = ["LOG", "ACCEPT"]
                    		action = rule['action'].upper()
		    		if action not in action_values:
                                    sys.exit('Action %s is not valid action! Please enter valid action (LOG or ACCEPT)' %(action)) 
                    		service = rule['service'].split('/')
			except KeyError, e:
				sys.exit('KeyError: Rule does not have key %s' %(e))
			
			if len(service) > 1:
                        	ps = Popen(["iptables", "-A", "testchain", "-p", service[0], "--dport", service[1], "-j", action], stdout=PIPE)
                        	ps1 = Popen(["iptables", "-A", "testchain", "-p", service[0], "--sport", service[1], "-j", action], stdout=PIPE)
                    	else:
                        	ps = Popen(["iptables", "-A", "testchain", "-p", service[0], "-j", action], stdout=PIPE)
                    	output = ps.communicate()[0]
                    	if output:
                        	print "Unable to add rule to chain due to: %s" %(output)
		    	count = count + 1
def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: %s json-blob' %sys.argv[0])
    else:
        json_blob = sys.argv[1]
    #'{"rule1": {"name": "tcp", "service": "tcp/80", "action" : "log"}, "rule2": { "name": "icmp", "service": "icmp", "action" : "log"}}'        
    test = ConfigureIPtables(json_blob)
    test.update_chain()

if __name__ == "__main__":
    main()
		
