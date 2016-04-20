import os.path
import pickle
from optparse import OptionParser
from threading import Thread, Lock
from product_key import *

CURRENT_PATH=os.path.abspath(__file__)
THIS_PATH = "/".join(CURRENT_PATH.split("/")[:-1])
KEYUPDATE = Lock()

def getKey():
    ''' Fetch the Key from product_key file, if productkey.pickle
        is not created. This will happen only once.
    '''
    productkeys= []
    if os.path.isfile(THIS_PATH +"/productkey.pickle"):
        with open(THIS_PATH +'/productkey.pickle', 'rb') as handle:
            productkeys = pickle.load(handle)

        for keyitem in productkeys:
            if keyitem["is_used"] == False:
                KEYUPDATE.acquire()
                productkeys[productkeys.index(keyitem)]["is_used"] = False
                with open(THIS_PATH +'/productkey.pickle', 'wb') as handle:
                    pickle.dump(productkeys, handle)
                KEYUPDATE.release()
                return keyitem["key"]

    else:
    ## This block will execute only once when 
        ## pickle file is not generated.
        productkeys = PRODUCT_KEYS
        for keyitem in productkeys:
            if keyitem["is_used"] == False:
                KEYUPDATE.acquire()
                productkeys[productkeys.index(keyitem)]["is_used"] = True
                with open(THIS_PATH +'/productkey.pickle', 'wb') as handle:
                    pickle.dump(productkeys, handle)
                KEYUPDATE.release()
                return keyitem["key"]

    return -1

def updateKey(key, status):
    if os.path.isfile(THIS_PATH +"/productkey.pickle"):
        with open(THIS_PATH +'/productkey.pickle', 'rb') as handle:
            productkeys = pickle.load(handle)
            for keyitem in productkeys:
                if keyitem["key"]==key:
                    productkeys[productkeys.index(keyitem)]["is_used"]=status
        with open(THIS_PATH +'/productkey.pickle', 'wb') as handle:
            pickle.dump(productkeys, handle)
            return True
    else:
        print "Key Not Found."
        return False


def addKey(newkey):
    if os.path.isfile(THIS_PATH +"/productkey.pickle"):
        productkeys= []
        with open(THIS_PATH +'/productkey.pickle', 'rb') as handle:
            productkeys = pickle.load(handle)
    ## Check if Key Entry is already there.
    for keyitem in productkeys:
        if keyitem["key"]==newkey:
            print newkey + " Key already present."
            return -1
    key_obj={"key": None, "is_used": None}
    key_obj["key"]=newkey
    key_obj["is_used"]= False
    KEYUPDATE.acquire()
    productkeys.append(key_obj)
    with open(THIS_PATH +'/productkey.pickle', 'wb') as handle:
        pickle.dump(productkeys, handle)
    KEYUPDATE.release()

def delKey(newkey):
    if os.path.isfile(THIS_PATH +"/productkey.pickle"):
        productkeys= []
        KEYUPDATE.acquire()
        with open(THIS_PATH +'/productkey.pickle', 'rb') as handle:
            productkeys = pickle.load(handle)
            for keyitem in productkeys:
                if keyitem["key"]==newkey:
                    if keyitem["is_used"]==False:
                        print "Warning: Are you sure to delete the Fresh Key (Press y/n)\n"
                        decision_inp = raw_input()
                        if decision_inp.upper()=="Y":
                            del(productkeys[productkeys.index(keyitem)])
                    else:
                        del(productkeys[productkeys.index(keyitem)])
        with open(THIS_PATH +'/productkey.pickle', 'wb') as handle:
            pickle.dump(productkeys, handle)
        KEYUPDATE.release()

def list_product_key_status():
    if os.path.isfile(THIS_PATH +"/productkey.pickle"):
        with open(THIS_PATH +'/productkey.pickle', 'rb') as handle:
            productkeys = pickle.load(handle)
            for keyitem in productkeys:
                print "key : ", keyitem["key"],
                print "\t        ",
                print "Is used status :", keyitem["is_used"]
    else:
        print "ALL KEYS are FRESH..."

def isvalidkey(key):
    split_key = key.split("-")
    valid_key = False
    for chunk in split_key[:-1]:
        if len(chunk)==5:
            valid_key = True
        else:
            valid_key = False
    if valid_key == True and len(split_key[-1])==7:
        return True
    else:
        return False


def main():
    parser = OptionParser()
    parser.add_option("-k", "--key", dest="key", default=False, type="string",
                  help="Add New Key")
    parser.add_option("-l", "--list", dest="list_display", default=False,action='store_true',
                  help="List Down the key status.")
    parser.add_option("-g", "--get", dest="get_key", default=False,action='store_true',
                  help="Get the unused key.")
    parser.add_option("-u", "--update", dest="update_key", default=False, type="string",
                  help="Update Key Status.")
    parser.add_option("-s", "--status", dest="status", default=False, type="string",
                  help="True or False")
    parser.add_option("-d", "--del", dest="del_key", default=False, type="string",
                  help="Delete Key from Persistent storage.")
    parser.add_option("-f", "--file", dest="key_file", default=False, type="string",
                  help="File containing pools of keys.")
    (options, args) = parser.parse_args()

    if options.key:
        if isvalidkey(options.key):
            addKey(options.key)
        else:
            print options.key, " is Invalid."
    if options.list_display==True:
        list_product_key_status()
    elif options.get_key==True:
        print getKey()
    elif options.update_key and options.status:
        if options.status.upper()=='FALSE':
            options.status = False
            updateKey(options.update_key , options.status)
        else:
            pass
    elif options.del_key:
        delKey(options.del_key)
    elif options.key_file:
        with open(options.key_file, "r") as key_file_handle:
            all_keys = key_file_handle.readlines()
            for key in all_keys[:-1]:
                if isvalidkey(key[:-1]):
                    addKey(key[:-1])
                else:
                    print key," is Invalid."
    else:
        pass

if __name__=='__main__':
    main()
    
                     
 
