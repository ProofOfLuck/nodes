from __future__ import print_function

import time
import json
import uuid

import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.httpclient
import tornado.gen

import setting
import tree
import node

working = False

def forward(seq):
    # global processed_message_ids

    # msg_id = seq[-1]
    # if msg_id in processed_message_ids:
    #     return
    # processed_message_ids.add(msg_id)
    msg = json.dumps(seq)

    for leader_node in LeaderHandler.leader_nodes:
        leader_node.write_message(msg)

    for leader_connector in LeaderConnector.leader_nodes:
        leader_connector.conn.write_message(msg)


# connect point from leader node
class LeaderHandler(tornado.websocket.WebSocketHandler):
    leader_nodes = set()

    def check_origin(self, origin):
        return True

    def open(self):
        self.from_host = self.get_argument("host")
        self.from_port = self.get_argument("port")
        # self.remove_node = True
        # if False: #temp disable force disconnect
        #     print(tree.current_port, "leader force disconnect")
        #     self.remove_node = False
        #     self.close()
        #     return

        print(tree.current_port, "leader connected")
        if self not in LeaderHandler.leader_nodes:
            LeaderHandler.leader_nodes.add(self)

    def on_close(self):
        print(tree.current_port, "leader disconnected")
        if self in LeaderHandler.leader_nodes: # and self.remove_node
            LeaderHandler.leader_nodes.remove(self)
        # self.remove_node = True

    @tornado.gen.coroutine
    def on_message(self, msg):
        seq = json.loads(msg)
        print(tree.current_port, "on message from leader connector", seq)

        if seq[0] == "NEW_BLOCK":
            miner.new_block(seq)

        forward(seq)


# connector to leader node
class LeaderConnector(object):
    """Websocket Client"""
    leader_nodes = set()

    def __init__(self, to_host, to_port):
        self.host = to_host
        self.port = to_port
        self.ws_uri = "ws://%s:%s/leader?host=%s&port=%s" % (self.host, self.port, tree.current_host, tree.current_port)
        # self.branch = None
        self.remove_node = False
        self.conn = None
        self.connect()

    def connect(self):
        tornado.websocket.websocket_connect(self.ws_uri,
                                callback = self.on_connect,
                                on_message_callback = self.on_message,
                                connect_timeout = 1000.0)

    def close(self):
        self.remove_node = True
        if self in LeaderConnector.leader_nodes:
            LeaderConnector.leader_nodes.remove(self)
        self.conn.close()

    def on_connect(self, future):
        print(tree.current_port, "leader connect")

        try:
            self.conn = future.result()
            if self not in LeaderConnector.leader_nodes:
                LeaderConnector.leader_nodes.add(self)
        except:
            print(tree.current_port, "reconnect leader on connect ...")
            tornado.ioloop.IOLoop.instance().call_later(1.0, self.connect)


    def on_message(self, msg):
        if msg is None:
            if not self.remove_node:
                print(tree.current_port, "reconnect leader on message...")
                # self.ws_uri = "ws://%s:%s/leader?host=%s&port=%s" % (self.host, self.port, tree.current_host, tree.current_port)
                tornado.ioloop.IOLoop.instance().call_later(1.0, self.connect)
            return

        seq = json.loads(msg)
        print(tree.current_port, "on message from leader", seq)

        if seq[0] == "NEW_BLOCK":
            miner.new_block(seq)

        # else:
        forward(seq)

transactions = []
def mining():
    # global working
    # print(tree.current_port, working)
    if working:
        tornado.ioloop.IOLoop.instance().call_later(1, mining)


current_leaders = set()
previous_leaders = set()
def update(leaders):
    global current_leaders
    global previous_leaders
    global working

    current_leaders = leaders
    if ("localhost", tree.current_port) in leaders - previous_leaders:
        for other_leader_addr in leaders:
            connected = set([(i.host, i.port) for i in LeaderConnector.leader_nodes]) |\
                        set([(i.from_host, i.from_port) for i in LeaderHandler.leader_nodes]) |\
                        set([(tree.current_host, tree.current_port)])
            if other_leader_addr not in connected:
                # print(tree.current_port, other_leader_addr, connected)
                LeaderConnector(*other_leader_addr)

                if not working:
                    tornado.ioloop.IOLoop.instance().add_callback(mining)
                working = True

    nodes_to_close = set()
    for node in LeaderConnector.leader_nodes:
        if (node.host, node.port) not in leaders:
            nodes_to_close.add(node)

    # print(tree.current_port, "nodes_to_close", len(nodes_to_close))
    while nodes_to_close:
        nodes_to_close.pop().close()


    if ("localhost", tree.current_port) not in leaders:
        working = False

        while LeaderConnector.leader_nodes:
            LeaderConnector.leader_nodes.pop().close()

    previous_leaders = leaders


if __name__ == '__main__':
    # main()
    print("run python node.py pls")
