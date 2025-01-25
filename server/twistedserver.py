from twisted.internet import reactor, ssl, defer
from twisted.internet.defer import Deferred, ensureDeferred 
from twisted.internet.protocol import Protocol, Factory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet.task import LoopingCall
import pickle
import bcrypt
import chess
from chessdatabase_json import ChessDatabase
import secrets
import uuid
import time
import asyncio
from random import randint


HOST = '127.0.0.1'
PORT = 65432
TOKEN_LENGTH = 32

chdata = ChessDatabase()
connected_clients = set()
logined_clients = {}

class ChessProtocol(NetstringReceiver):
    def connectionMade(self):
        self.addr = self.transport.getPeer()
        connected_clients.add(self)
        print(f"Player connected: {self.addr}")

    def connectionLost(self, reason):
        connected_clients.discard(self)

        session_to_remove = None
        for session_id, details in logined_clients.items():
            if details["connection"] == self:
                session_to_remove = session_id
                username = ensureDeferred(chdata.find_user_by_session(session_to_remove))
                break

        if session_to_remove:
            logined_clients.pop(session_to_remove, None)
            
            disconnected_games = ensureDeferred(chdata.get_games_involving(username))
            for game in disconnected_games:
                opponent_username = (
                    game["white"] if game["black"] == username else game["black"]
                )
                opponent_session_id = (
                    game["whitesess"] if game["black"] == username else game["blacksess"]
                )
                if opponent_session_id in logined_clients:
                    opponent_conn = logined_clients[opponent_session_id]["connection"]
                    opponent_conn.send_message({"type": "opponent_disconnected"})
                ensureDeferred(chdata.remove_game(game["game_id"]))

        print(f"Player disconnected: {self.addr} |:| reason {reason}")

    def stringReceived(self, data):
        try:
            message = pickle.loads(data)
            print(message)
            if "type" not in message:
                self.send_error("Invalid message format")
                return
            
            message_type = message["type"]
            handler = getattr(self, f"handle_{message_type}", None)
            if handler:
                ensureDeferred(handler(message))
            else:
                self.send_error("Unknown message type")
        except Exception as e:
            print(f"Error with player {self.addr}: {e}")

    def send_message(self, message):
        data = pickle.dumps(message)
        self.sendString(data)

    def send_error(self, reason):
        self.send_message({"type": "error", "reason": reason})
        
    async def process_tokenauth(self, message):
        token = message["token"]
        username = message["username"]
        usersession = await chdata.find_session(username)
        if not usersession:
            self.send_error("Unauthorized")
            return (None, None)

        if logined_clients[usersession]["token"] != token:
            self.send_error("Unauthorized")
            return (None, None)
        
        return username, usersession

    # Handlers for different message types
    async def handle_register(self, message):
        username = message["username"]
        password = message["password"]
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        success = await chdata.add_user(username, hashed_password)

        if success:
            self.send_message({"type": "register_success"})
        else:
            self.send_message({"type": "register_failed", "reason": "Username already exists"})

    async def handle_login(self, message):
        username = message["username"]
        password = message["password"]
        user = await chdata.find_user(username)
        print("letsago")

        if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
            token = secrets.token_hex(TOKEN_LENGTH)
            session_id = str(uuid.uuid4())
            logined_clients[session_id] = {"token":token, "connection":self}
            await chdata.add_session(username, session_id)
            elo = await chdata.get_elo(username)
            self.send_message({"type": "login_success", "username": username, "token": token, "elo": elo})
        else:
            self.send_message({"type": "login_failed", "reason": "Invalid credentials"})
            
            
    async def find_match(self, username, session_id, rating):
        best_match = None
        best_diff = float('inf')
        current_time = time.time()
        elo_range = 50  

        while True:
            queue = await chdata.get_queue()
            for player in queue:
                if player["session_id"] == session_id:
                    continue

                diff = abs(player["rating"] - rating)
                if diff <= elo_range:
                    if diff < best_diff:
                        best_match = player
                        best_diff = diff

            if best_match:
                queue = [p for p in queue if p["session_id"] != best_match["session_id"] and p["session_id"] != session_id]
                await chdata.restore_queue(queue)
                return best_match

            if current_time + 5 < time.time(): 
                elo_range += 50
                current_time = time.time()

            def sleep_callback():
                pass  
        
            defered = defer.Deferred()
            reactor.callLater(0.5, lambda: defered.callback(True))
            await defered

    async def handle_find_game(self, message):
        username, usersession = await self.process_tokenauth(message)
        
        if username == None:
            return
        
        elo = await chdata.get_elo(username)

        await chdata.add_to_queue(username, usersession, elo)
        
        elo = await chdata.get_elo(username)
        opponent = await self.find_match(username, usersession, elo)

        if opponent:
            board = chess.Board()
            opponent_conn = logined_clients[opponent["session_id"]]["connection"]
            if randint(0, 1) % 2 == 0:
                username_color = "white"
                opponent_color = "black"
            else:
                username_color = "black"
                opponent_color = "white"

            game_id = await chdata.create_game(
                white_username=username if username_color == "white" else opponent["username"],
                whitesess=usersession if username_color == "white" else opponent["session_id"],
                black_username=username if username_color == "black" else opponent["username"],
                blacksess=usersession if username_color == "black" else opponent["session_id"],
                board_fen=board.fen(),
            )

            self.send_message({"type": "game_start", "color": username_color, "game_id": game_id, "board": board.fen()})
            opponent_conn.send_message({"type": "game_start", "color": opponent_color, "game_id": game_id, "board": board.fen()})
            
    def calculate_elo(self, current_rating, opponent_rating, score, k_factor=32):
        expected_score = 1 / (1 + 10 ** ((opponent_rating - current_rating) / 400))
        new_rating = current_rating + k_factor * (score - expected_score)
        return round(new_rating)

    async def handle_move(self, message):
        username, usersession = await self.process_tokenauth(message)
        
        if username == None:
            return

        game_id = message["game_id"]
        move = message["move"]
        game = await chdata.find_game(game_id)

        if not game:
            self.send_error("Game not found")
            return

        board = chess.Board(game["board_fen"] if game["board_fen"] else None)
        if move in [m.uci() for m in board.legal_moves]:
            board.push_uci(move)
            await chdata.update_game(game_id, board.fen())
            self.send_message({"type": "update", "move": move})

            opponent_color = "white" if username == game["black"] else "black"
            opponent_conn = logined_clients[game[f"{opponent_color}sess"]]["connection"]
            opponent_conn.send_message({"type": "update", "move": move})

            if board.is_game_over():
                result = board.result()
                winner = "white" if result == "1-0" else "black" if result == "0-1" else "draw"
                whiteelo = await chdata.get_elo(game["white"])
                blackelo = await chdata.get_elo(game["black"])
                
                if winner == "white":
                    white_score, black_score = 1, 0
                elif winner == "black":
                    white_score, black_score = 0, 1
                else:  
                    white_score, black_score = 0.5, 0.5
                
                new_white_elo = self.calculate_elo(whiteelo, blackelo, white_score)
                new_black_elo = self.calculate_elo(blackelo, whiteelo, black_score)
                
                await chdata.update_elo(game["white"], new_white_elo)
                await chdata.update_elo(game["black"], new_black_elo)
    
                whiteconn = logined_clients[game["whitesess"]]["connection"]
                blackconn = logined_clients[game["blacksess"]]["connection"]
                
                whiteconn.send_message({"type": "game_end", "winner": winner, "elo": new_white_elo})
                blackconn.send_message({"type": "game_end", "winner": winner, "elo": new_black_elo})
        else:
            self.send_error("Illegal move")

    async def handle_logout(self, message):
        username, usersession = await self.process_tokenauth(message)
        
        if username == None:
            return
        
        logined_clients.pop(usersession)
        
        await chdata.delete_session(usersession)


class ChessFactory(Factory):
    def buildProtocol(self, addr):
        return ChessProtocol()
    
    
def shutdown():
    """Clean up resources on server shutdown."""
    print("Shutting down server...")
    for client in connected_clients:
        client.transport.loseConnection()
    connected_clients.clear()
    logined_clients.clear()
    print("Server shut down successfully.")


if __name__ == "__main__":
    print("Secure Chess Server started with Twisted. Waiting for players...")

    # Add a system event trigger for graceful shutdown
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)

    try:
        reactor.listenTCP(PORT, ChessFactory())
        reactor.run()
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Stopping the server...")
        reactor.stop()