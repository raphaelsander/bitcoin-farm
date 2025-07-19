#!/usr/bin/python3

# Library documentation: https://bitcoinlib.readthedocs.io/
from bitcoinlib.keys import HDKey
from bitcoinlib import mnemonic
# Library documentation: https://docs.python.org/3/library/logging.html
import logging
from multiprocessing import Queue, Process, current_process
import json
import base64
from time import sleep, time
from hashlib import sha256
import argparse
import zipfile
import os

# Requests libraries for rate limiting and retries
from requests_ratelimiter import LimiterAdapter
from requests.packages.urllib3.util.retry import Retry
from requests import Session


# Logging configuration
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# starting some variables
start_time = time()
total_verified = 0
pos_file = "logs/position.txt"


def consume_wordlist(wordlist_queue, addresses_queue, wordlist, pos_file):
    if zipfile.is_zipfile(wordlist):
        zip_filename = wordlist
        inner_filename = "wordlist.txt"

        try:
            last_position = int(open(pos_file).read())
        except (FileNotFoundError, ValueError):
            last_position = 0

        try:
            with zipfile.ZipFile(zip_filename, 'r') as zip_file:
                with zip_file.open(inner_filename, 'r') as file:
                    file.seek(last_position)
                    for line in file:
                        word = {
                            "seek_position": last_position,
                            "word": line.strip(),
                            "size": len(line)
                        }
                        logger.debug(status)

                        while wordlist_queue.qsize() > 10000:
                            sleep(1)
                        wordlist_queue.put(word)

                        last_position += len(line)
                
        except KeyboardInterrupt:
            with open(pos_file, "w") as pos_file:
                pos_file.write(str(last_position))
            exit(0)

    try:
        last_position = int(open(pos_file).read())
    except (FileNotFoundError, ValueError):
        last_position = 0

    try:
        # Process each line of the wordlist and add to the wordlist queue to
        # worker process consume and generate the wallets, but this queue is
        # limited to 10000 items to avoid high consumption of resources
        with open(wordlist, 'rb') as file:
            file.seek(last_position)
            for line in file:
                word = {
                    "seek_position": last_position,
                    "word": line.strip(),
                    "size": len(line)
                }
                logger.debug(word)

                while wordlist_queue.qsize() > 10000:
                    sleep(1)
                wordlist_queue.put(word)

                last_position += len(line)

        # This sleep time is to prevent that the end of queue (None) to be added
        # to addresses queue before start the workers processes.
        sleep(5)
        
        # Wait wordlist queue and addresses queue get empty before send the end
        # of queue (None) to address queue
        while not wordlist_queue.empty() or not addresses_queue.empty():
            sleep(1)
        
        # Adding the None to address queue will indicate that the queues are
        # empty and exit checker process
        logger.info("wordlist and queues exhausted")
        logger.debug("sending signal to stop checker process")
        addresses_queue.put(None)

    except Exception as e:
        logger.error(f"Error during consume wordlist: {e}")
    
    # finally:
    #     logger.info("KeyboardInterrupt received...")
    #     with open(pos_file, "w") as pos_file:
    #         pos_file.write(str(last_position))
        
    #     # Wait wordlist queue and addresses queue get empty before send the end
    #     # of queue (None) to address queue
    #     while not wordlist_queue.empty() or not addresses_queue.empty():
    #         sleep(1)
        
    #     # Adding the None to address queue will indicate that the queues are
    #     # empty and exit checker process
    #     logger.debug("sending signal to stop checker process")
    #     addresses_queue.put(None)
        
    #     exit(0)


def generate_addresses(addresses_queue, derivation_path, depth):
    try:
        password='bitcoin'
        while True:
            if addresses_queue.qsize() < 4000:
                passphrase = mnemonic.Mnemonic(language='english').generate(
                    strength=128,
                    add_checksum=True
                )

                seed = mnemonic.Mnemonic().to_seed(passphrase, password)
                
                wallet = HDKey.from_seed(
                    seed,
                    witness_type='segwit'
                )

                if derivation_path:

                    for address_index in range(0, depth):

                        path = f"m/84'/0'/0'/0/{address_index}"
                        
                        subkey = wallet.subkey_for_path(path)

                        public_key = subkey.subkey_for_path(path).address()
                        private_key = subkey.subkey_for_path(path).wif_key()
                        
                        address = {
                            "passphrase": passphrase,
                            "password": password,
                            "seed": seed.hex(),
                            "path": path,
                            "private_key": private_key,
                            "public_key": public_key
                        }

                        logger.debug(address)

                        addresses_queue.put(address)

                # Private key in WIF (Wallet Import Format) compressed and encoded in Base58
                private_key_wif = wallet.wif_key()
                
                # Public legacy address in compressed format encoded in Base58
                public_key_address = wallet.address()

                address = {
                    "passphrase": passphrase,
                    "password": password,
                    "private_key": f"segwit:{private_key_wif}",
                    "public_key": public_key_address
                }

                logger.debug(address)

                addresses_queue.put(address)
            else:
                sleep(1)
    except KeyboardInterrupt:
        print(f"generator process interrupted ({current_process().name})")


def generate_wallets(wordlist_queue, addresses_queue, derivation_path, depth):
    try:
        while True:
            while addresses_queue.qsize() > 10000:
                sleep(1)
            if wordlist_queue.empty():
                sleep(1)
            else:
                word = wordlist_queue.get()
                raw_private_key = word["word"]
                seek_position = word["seek_position"]
                private_key_hex = sha256(raw_private_key).digest()

                addr_type = {
                    "p2pkh": {
                        "type": "legacy",
                        "path": "m/44'/0'/0'",
                        "electrum_type": "p2pkh"
                    },
                    "p2sh": {
                        "type": "p2sh-segwit",
                        "path": "m/49'/0'/0'",
                        "electrum_type": "p2wpkh-p2sh"
                    },
                    "p2wphk": {
                        "type": "segwit",
                        "path": "m/84'/0'/0'",
                        "electrum_type": "p2wpkh"
                    }
                }

                for addr_type_index in addr_type:

                    wallet = HDKey(
                        private_key_hex,
                        witness_type=f"{addr_type[addr_type_index]['type']}"
                    )

                    if derivation_path:

                        for addr_index in range(0, depth):

                            path = f"{addr_type[addr_type_index]['path']}/0/{addr_index}"
                            subkey = wallet.subkey_for_path(path)

                            public_key = subkey.subkey_for_path(path).address()
                            private_key = subkey.subkey_for_path(path).wif_key()
                            
                            address = {
                                "passphrase": raw_private_key,
                                "seek_position": seek_position,
                                "path": path,
                                "private_key": private_key,
                                "public_key": public_key
                            }

                            logger.debug(address)

                            addresses_queue.put(address)

                    # Private key in WIF (Wallet Import Format) compressed and encoded in Base58
                    private_key_wif = wallet.wif_key()
                    
                    # Public legacy address in compressed format encoded in Base58
                    public_key_address = wallet.address()

                    address = {
                        "passphrase": raw_private_key,
                        "seek_position": seek_position,
                        "private_key": f"{addr_type[addr_type_index]['electrum_type']}:{private_key_wif}",
                        "public_key": public_key_address
                    }

                    logger.debug(address)

                    addresses_queue.put(address)
    except KeyboardInterrupt:
        print(f"generator process interrupted ({current_process().name})")
    except Exception as e:
        logger.error(f"error during wallet generation: {e}")


def save_filtered_addresses(filtered_address):
    def custom_serializer(obj):
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('utf-8')
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    
    try:
        json_dump = json.dumps(filtered_address, default=custom_serializer)
        f = open("logs/keys.txt", "a")
        f.write(f"{json_dump}\n")
        f.close()
    
    except TypeError as e:
        print(f"Erro: {e}")


def check_public_keys(addresses, session):
    
    public_keys = []
    for address in addresses:
        public_keys.append(address['public_key'])
    
    try:
        url = "https://blockchain.info/balance?active=" + "|".join(public_keys)
        response = session.get(url)
        
        if response.status_code == 200:
            content = response.content

            addresses_status = json.loads(content.decode("utf-8"))
            
            filtered_addresses = [
                addr for addr in addresses
                if addresses_status[
                    addr['public_key']
                ]['final_balance'] != 0 or
                addresses_status[
                    addr['public_key']
                ]['total_received'] != 0 or
                addresses_status[
                    addr['public_key']
                ]['n_tx'] != 0
            ]

            if filtered_addresses:
                for filtered_address in filtered_addresses:
                    logger.info(filtered_address)
                    save_filtered_addresses(filtered_address)

        else:
            status = {
                "request": response.url,
                "status_code": response.status_code,
                "response": response.text
            }
            logger.warning(status)
    
    except Exception as e:
        logger.warning(e)


def show_status(total_verified, addresses_queue_size, wordlist_queue): 
    check_per_seconds = total_verified / (time() - start_time)
    status = {
        "total": total_verified,
        "check_per_second": check_per_seconds,
        "address_queue_size": addresses_queue_size
    }
    if wordlist_queue:
        status["wordlist_queue_size"] = wordlist_queue.qsize()

    logger.info(status)


def create_logs_directory():
    try:
        os.mkdir("logs")
        logger.info("logs directory created")

    except FileExistsError:
        logger.warning("the directory logs exist")
    
    if not os.access("logs", os.W_OK):
        logger.error("logs directory without write permission")
        exit(1)


def check_addresses(addresses_queue, wordlist_queue, mnemonic, pos_file):
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = LimiterAdapter(per_second=10, max_retries=retry_strategy)

    session = Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        max_addresses = 137
        total_verified = 0
        count = 0

        while True:
            addresses = []
            
            for _ in range(0, max_addresses):
                while addresses_queue.empty():
                    sleep(1)
                
                address = addresses_queue.get()
                
                # If None, indicates that queue is done
                if address == None:
                    # If addresses is empty no request to blockchain.info is needed
                    if addresses:
                        check_public_keys(addresses, session)
                        show_status(len(addresses), addresses_queue.qsize())
                        
                        logger.info(
                            f'stopping checker process '
                            f'(name: {current_process().name}, '
                            f'pid: {current_process().pid})'
                        )

                        exit(0)
                else:
                    addresses.append(address)
            
            check_public_keys(addresses, session)

            total_verified += len(addresses)
            count += 1
            if count % 100 == 0:
                if not mnemonic:
                    with open(pos_file, "w") as file:
                        file.write(str(address["seek_position"]))
                show_status(total_verified, addresses_queue.qsize(), wordlist_queue)
    
    except KeyboardInterrupt:
        print(f"checker process interrupted ({current_process().name})")


def create_workers(addresses_queue=None, derivation_path=None, depth=None, wordlist_queue=None):

    num_workers = 4
    workers_processes = []

    for i in range(num_workers):
        if wordlist_queue == None:
            process = Process(
                name=f'worker_wallet_creator_{i}',
                target=generate_addresses,
                args=(addresses_queue, derivation_path, depth)
            )
            process.start()
            workers_processes.append(process)
        else:
            process = Process(
                name=f'worker_wallet_creator_{i}',
                target=generate_wallets,
                args=(wordlist_queue, addresses_queue, derivation_path, depth)
            )
            process.start()
            workers_processes.append(process)
    
    return workers_processes


def create_checker(addresses_queue, wordlist_queue=None, mnemonic=False):
    process = Process(
        name='checker_addresses',
        target=check_addresses,
        args=(addresses_queue, wordlist_queue, mnemonic, pos_file)
    )
    process.start()

    return process


def main():
    create_logs_directory()

    parser = argparse.ArgumentParser(
        prog='bitcoin-farm',
        description='This software bruteforce Bitcoin wallets and check if was used before',
        epilog='Donation: 1MZhK28TfBVGunXqkarCu7BSCUHXrEQbcV'
    )

    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='comando a executar'
    )

    # wordlist command
    wordlis_parser = subparsers.add_parser(
        'wordlist',
        help='process wordlist'
    )
    wordlis_parser.add_argument(
        '--path', required=True,
        help='wordlist path'
    )
    wordlis_parser.add_argument(
        '--derivation-path',
        action='store_true',
        help='verifiy derivation keys'
    )
    wordlis_parser.add_argument(
        '--depth',
        type=int,
        default=20,
        help='derivation keys depth'
    )

    # mnemonic command
    mnemonic_parser = subparsers.add_parser(
        'mnemonic',
        help='gera ou processa mnemonics'
    )
    mnemonic_parser.add_argument(
        '--derivation-path',
        action='store_true',
        help='ativa o uso de derivation path'
    )
    mnemonic_parser.add_argument(
        '--depth',
        type=int,
        default=20,
        help='nível de profundidade para derivação'
    )

    args = parser.parse_args()

    if args.command == 'wordlist':
        process_wordlist(
            path=args.path,
            derivation=args.derivation_path,
            depth=args.depth
        )
    elif args.command == 'mnemonic':
        process_mnemonic(
            derivation=args.derivation_path,
            depth=args.depth
        )


def process_wordlist(path, derivation, depth):
    addresses_queue = Queue()
    wordlist_queue = Queue()

    workers_processes = create_workers(
        addresses_queue,
        derivation,
        depth,
        wordlist_queue
    )
    checker_process = create_checker(addresses_queue, wordlist_queue)

    consume_wordlist_process = Process(
        name='consume_wordlist_process',
        target=consume_wordlist,
        args=(wordlist_queue, addresses_queue, path, pos_file)
    )
    consume_wordlist_process.start()

    try:
        consume_wordlist_process.join()
        checker_process.join()

        for process in workers_processes:
            logger.info(f"stopping worker process (name: {process.name}, pid: {process.pid})")
            process.terminate()
    
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, terminating processes.")
        
        checker_process.terminate()
        consume_wordlist_process.terminate()
        for process in workers_processes:
            process.terminate()
        
        checker_process.join()
        consume_wordlist_process.join()
        for process in workers_processes:
            process.join()

def process_mnemonic(derivation, depth):
    addresses_queue = Queue()
    workers_processes = create_workers(
        addresses_queue,
        derivation,
        depth
    )
    checker_process = create_checker(addresses_queue, mnemonic=True)
    try:
        checker_process.join()

        for process in workers_processes:
            logger.info(f"stopping worker process (name: {process.name}, pid: {process.pid})")
            process.terminate()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, terminating processes.")
        
        checker_process.terminate()
        for process in workers_processes:
            process.terminate()
        
        checker_process.join()
        for process in workers_processes:
            process.join()

if __name__ == '__main__':
    main()
