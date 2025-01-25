from twisted.internet import reactor, protocol
from twisted.protocols.basic import NetstringReceiver
import chess
import queue
import pickle
import threading
import traceback


class ChessModelProtocol(NetstringReceiver):
    def connectionMade(self):
        print("Connected to the server.")
        self.factory = self.factory  # This will be set by Twisted automatically
        self.factory.client_connection = self
        self.factory.on_connection()

    def connectionLost(self, reason):
        print(f"Connection lost: {reason}")
        self.factory.client_connection = None

    def stringReceived(self, data):
        try:
            message = pickle.loads(data)
            self.factory.handle_server_message(message)
        except Exception as e:
            print(f"Error processing server message: {e}")

    def send_to_server(self, message):
        try:
            serialized_message = pickle.dumps(message)
            self.sendString(serialized_message)
        except Exception as e:
            print(f"Error sending message to server: {e}")


class ChessModelFactory(protocol.ClientFactory):
    protocol = ChessModelProtocol  # Reference to the protocol class, not an instance

    def __init__(self, model):
        self.model = model
        self.client_connection = None

    def on_connection(self):
        self.model.on_connection()

    def handle_server_message(self, message):
        self.model.on_server_message(message)

    def clientConnectionFailed(self, connector, reason):
        print(f"Connection failed: {reason}")
        self.model.stop()

    def clientConnectionLost(self, connector, reason):
        print(f"Connection lost: {reason}")
        traceback.print_exc()
        self.model.stop()


class ChessModel:
    def __init__(self, server_host="127.0.0.1", server_port=65432):
        self.board = None

        self.server_host = server_host
        self.server_port = server_port

        self.response_queue = queue.Queue()
        self.username = None
        self.color = None
        self.token = None
        self.game_id = None
        self.waiting_for_opponent = True

        self.reactor_thread = None
        self.factory = ChessModelFactory(self)
        self.reactor_started = False

    def connect_to_server(self):
        try:
            self.reactor_thread = threading.Thread(target=self._start_reactor, daemon=True)
            self.reactor_thread.start()

            reactor.connectTCP(self.server_host, self.server_port, self.factory)
            return True
        except Exception as e:
            print(f"Server connection issue: {e}")
            return False

    def _start_reactor(self):
        try:
            reactor.run(installSignalHandlers=False)  # Start the reactor without blocking
        except Exception as e:
            print(f"Reactor error: {e}")

    def stop(self):
        self.response_queue.put({"type": "conn_loss"})
        reactor.stop()

    def on_connection(self):
        print("Connection established. Ready to communicate.")

    def on_server_message(self, message):
        print(f"Received message from server: {message}")
        self.response_queue.put(message)

    def get_response(self):
        try:
            return self.response_queue.get_nowait()
        except queue.Empty:
            return None

    def send_to_server(self, message):
        if self.token:
            message["token"] = self.token

        if self.factory.client_connection:
            self.factory.client_connection.send_to_server(message)
        else:
            print("No active connection to the server.")

    def register(self, username, password):
        self.send_to_server({"type": "register", "username": username, "password": password})

    def login(self, username, password):
        self.send_to_server({"type": "login", "username": username, "password": password})
        
    def logout(self): 
        self.send_to_server({"type": "logout", "username": self.username})

    def find_game(self):
        self.send_to_server({"type": "find_game", "username": self.username})

    def send_move_to_server(self, move):
        if self.token and self.game_id:
            self.send_to_server({
                "type": "move",
                "move": move.uci(),
                "color": self.color,
                "game_id": self.game_id,
            })
        else:
            print("Unable to make a move: Not authenticated or game not started.")

    def make_move(self, move):
        self.board.push(move)