from __future__ import print_function

import time
import json
import uuid
import hashlib
import copy

import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.httpclient
import tornado.gen


import setting
import tree
import node
import leader
import database


def longest_chain(root_hash = '0'*64):
    roots = database.connection.query("SELECT * FROM chain"+tree.current_port+" WHERE prev_hash = %s ORDER BY nonce", root_hash)

    chains = []
    prev_hashs = []
    for root in roots:
        # chains.append([root.hash])
        chains.append([root])
        prev_hashs.append(root.hash)

    while True:
        if prev_hashs:
            prev_hash = prev_hashs.pop(0)
        else:
            break

        leaves = database.connection.query("SELECT * FROM chain"+tree.current_port+" WHERE prev_hash = %s ORDER BY nonce", prev_hash)
        if len(leaves) > 0:
            for leaf in leaves:
                for c in chains:
                    if c[-1].hash == prev_hash:
                        chain = copy.copy(c)
                        # chain.append(leaf.hash)
                        chain.append(leaf)
                        chains.append(chain)
                        break
                if leaf.hash not in prev_hashs and leaf.hash:
                    prev_hashs.append(leaf.hash)

    longest = None
    for i in chains:
        # print(i)
        if not longest:
            longest = i
        if len(longest) < len(i):
            longest = i
    return longest


nonce = 0
def mining():
    global nonce

    longest = longest_chain()
    # print(longest)
    if longest:
        longest_hash = longest[-1].hash
        difficulty = longest[-1].difficulty
        identity = longest[-1].identity
        data = longest[-1].data
        recent = longest[-3:]
        # print(recent)
        if len(recent) * setting.BLOCK_INTERVAL_SECONDS > recent[-1].timestamp - recent[0].timestamp:
            new_difficulty = min(255, difficulty + 1)
        else:
            new_difficulty = max(1, difficulty - 1)

        if tree.current_port in [i.identity for i in longest[-6:]]:
            return

    else:
        longest_hash, difficulty, new_difficulty, data, identity = "0"*64, 1, 1, "", ""

    for i in range(100):
        block_hash = hashlib.sha256((identity + data + longest_hash + str(difficulty) + str(nonce)).encode('utf8')).hexdigest()
        if int(block_hash, 16) < int("1" * (256-difficulty), 2):
            if longest:
                print(len(longest), longest[-1].timestamp, longest[0].timestamp, longest[-1].timestamp - longest[0].timestamp)
            # db.execute("UPDATE chain SET hash = %s, prev_hash = %s, nonce = %s, wallet_address = %s WHERE id = %s", block_hash, longest_hash, nonce, wallet_address, last.id)
            # database.connection.execute("INSERT INTO chain"+tree.current_port+" (hash, prev_hash, nonce, difficulty, identity, timestamp, data) VALUES (%s, %s, %s, %s, '')", block_hash, longest_hash, nonce, difficulty, str(tree.current_port))

            message = ["NEW_BLOCK", block_hash, longest_hash, nonce, new_difficulty, str(tree.current_port), int(time.time()), {}, uuid.uuid4().hex]
            tree.forward(message)
            # print(tree.current_port, "mining", nonce, block_hash)
            nonce = 0
            break

        nonce += 1

def new_block(seq):
    msg_header, block_hash, longest_hash, nonce, difficulty, identity, timestamp, data, msg_id = seq
    try:
        database.connection.execute("INSERT INTO chain"+tree.current_port+" (hash, prev_hash, nonce, difficulty, identity, timestamp, data) VALUES (%s, %s, %s, %s, %s, %s, %s)", block_hash, longest_hash, nonce, difficulty, identity, timestamp, json.dumps(data))
    except:
        pass

    longest = longest_chain()
    if longest:
        leaders = set([("localhost", i.identity) for i in longest[-6:-3]])
        leader.update(leaders)

def main():
    print(tree.current_port, "miner")

    mining_task = tornado.ioloop.PeriodicCallback(mining, 1000) # , jitter=0.5
    mining_task.start()

if __name__ == '__main__':
    print("run python node.py pls")
