# Bitcoin Farm

![img.png](imgs/btc_numbers.png)

Bitcoin Farm is a simple script in Python what test you lucky.  
We are able to understand the number of Bitcoin wallet in the world is equal to:

**(964934076977634961863091541739065898773646368992290869855043026179318012451 - 1) * 128 + 127**

or

**~1,23 * (10 ^ 77)**

Reference: <https://allbitcoinprivatekeys.com/>

We have about 10 ^ 23 of sand points in the Earth. A big difference.  
It's more ease find a specific sand point instead a Bitcoin wallet with money.

But if you find any wallet with money, what do you do?
Write your answers in this [issue](https://github.com/raphaelsander/Bitcoin-Farm/issues/2)

---

## To run in Docker container

1 - Create a Bitcoin Farm volume to save the wallet with money and transactions:
```bash
$ docker volume create bitcoinfarm_volume
```

2 - Build the image
```bash
$ docker build -t bitcoinfarm .
```

3 - Run the container:
```bash
$ docker run -d \
  --name bitcoinfarm \
  -e PYTHONUNBUFFERED=1 \
  --mount source=bitcoinfarm_volume,target=/usr/src/app/logs \
  bitcoinfarm
```