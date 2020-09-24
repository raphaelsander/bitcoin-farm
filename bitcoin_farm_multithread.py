#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

## Dependencias
# apt install python-bs4

import requests
import random
import urllib3
from bs4 import BeautifulSoup
from threading import Thread
import os

urllib3.disable_warnings()

class Th(Thread):
    def __init__(self, num):
        Thread.__init__(self)
        self.num = num
    def run(self):
        while True:
            page = random.randint(0, 904625697166532776746648320380374280100293470930272690489102837043110636675)
            try:
                req = requests.get("https://lbc.cryptoguru.org/dio/%s" %page, verify=False)
                if req.status_code == 200:
                    print("Page: %s" %page)
                    content = req.content
                    soup = BeautifulSoup(content, 'html.parser')
                    all_span = soup.find_all(name='span')
                    list = []
                    for x in all_span:
                        list.append(x.get_text().split())
                    
                    for x in range(0, 256, 2):
                        
                        req2 = requests.get("https://blockchain.info/q/addressbalance/%s" %list[x][2])

                        if req2.status_code == 200:
                            content2 = req2.content
                                
                            if content2 != "0":
                                output = ("PrivateKey: %s : PublicKey: %s" %(list[x][1], list[x][2]))
                                print(output)
                                os.system('echo %s >> keys.txt' %page)
                                os.system('echo %s >> keys.txt' %output)
            except:
                print("Erro - Page: %s" %page)

for x in range(1, 20):
	a = Th(x)
	a.start()
