import asyncio
import json
import time
from pathlib import Path
from typing import Optional

class ChessDatabase:
    def __init__(self, base_path="data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.users_file = self.base_path / "users.json"
        self.sessions_file = self.base_path / "sessions.json"
        self.player_queue_file = self.base_path / "player_queue.json"
        self.games_file = self.base_path / "games.json"

        self._initialize_file(self.users_file, [])
        self._initialize_file(self.sessions_file, [])
        self._initialize_file(self.player_queue_file, [])
        self._initialize_file(self.games_file, [])

    def _initialize_file(self, file_path, default_data):
        if not file_path.exists():
            file_path.write_text(json.dumps(default_data))

    async def _read_file(self, file_path):
        async with asyncio.Lock():
            return json.loads(file_path.read_text())

    async def _write_file(self, file_path, data):
        async with asyncio.Lock():
            file_path.write_text(json.dumps(data, indent=4))

    async def add_user(self, username, hashed_password, rating=1200):
        users = await self._read_file(self.users_file)
        if any(user["username"] == username for user in users):
            return False
        users.append({"username": username, "password": hashed_password, "session_id": "", "rating": rating})
        await self._write_file(self.users_file, users)
        return True

    async def find_user(self, username):
        users = await self._read_file(self.users_file)
        return next((user for user in users if user["username"] == username), None)

    async def get_elo(self, username):
        user = await self.find_user(username)
        return user["rating"] if user else None
    
    async def update_elo(self, username, elo):
        users = await self._read_file(self.users_file)
        for user in users:
            if user["username"] == username:
                user["rating"] = elo
                break
        await self._write_file(self.users_file, users)

    async def add_session(self, username, session_id):
        users = await self._read_file(self.users_file)
        for user in users:
            if user["username"] == username:
                user["session_id"] = session_id
                break
        await self._write_file(self.users_file, users)

    async def find_user_by_session(self, session_id):
        users = await self._read_file(self.users_file)
        return next((users for user in users if user["session_id"] == session_id), None)
    
    async def find_session(self, username):
        users = await self._read_file(self.users_file)
        for user in users:
            if user["username"] == username:
                return user["session_id"]
        else:
            return None

    async def delete_session(self, session_id):
        users = await self._read_file(self.sessions_file)
        for user in users:
            if "session" in user and user["session"]["session_id"] == session_id:
                user["session"] = ""
                break
        await self._write_file(self.sessions_file, users)

    async def add_to_queue(self, username, session_id, rating):
        queue = await self._read_file(self.player_queue_file)
        queue.append({"username": username, "session_id": session_id, "rating": rating, "queueStartTime": time.time()})
        await self._write_file(self.player_queue_file, queue)

    async def get_oldest_in_queue(self):
        queue = await self._read_file(self.player_queue_file)
        if queue:
            oldest = queue.pop(0)
            await self._write_file(self.player_queue_file, queue)
            return oldest
        return None

    async def clear_queue(self, username):
        queue = await self._read_file(self.player_queue_file)
        queue = [player for player in queue if player["username"] != username]
        await self._write_file(self.player_queue_file, queue)

    async def create_game(self, white_username, whitesess, black_username, blacksess, board_fen):
        games = await self._read_file(self.games_file)
        game_id = str(len(games) + 1)
        games.append({
            "game_id": game_id,
            "white": white_username,
            "whitesess": whitesess,
            "black": black_username,
            "blacksess": blacksess,
            "board_fen": board_fen,
            "status": "ongoing"
        })
        await self._write_file(self.games_file, games)
        return game_id

    async def update_game(self, game_id, board_fen):
        games = await self._read_file(self.games_file)
        for game in games:
            if game["game_id"] == game_id:
                game["board_fen"] = board_fen
                break
        await self._write_file(self.games_file, games)

    async def find_game(self, game_id):
        games = await self._read_file(self.games_file)
        return next((game for game in games if game["game_id"] == game_id), None)

    async def end_game(self, game_id, winner):
        games = await self._read_file(self.games_file)
        for game in games:
            if game["game_id"] == game_id:
                game["status"] = "completed"
                game["winner"] = winner
                break
        await self._write_file(self.games_file, games)

    async def delete_local_databases(self):
        users = await self._read_file(self.sessions_file)
        for user in users:
            if "session" in user:
                user["session"] = ""
        await self._write_file(self.users_file, users)
        await self._write_file(self.player_queue_file, [])
        await self._write_file(self.games_file, [])
        
    async def get_games_involving(self, username):
        games = await self._read_file(self.games_file)
        return [game for game in games if game["white"] == username or game["black"] == username]

    async def remove_game(self, game_id):
        games = await self._read_file(self.games_file)
        games = [game for game in games if game["game_id"] != game_id]
        await self._write_file(self.games_file, games)
        
    async def get_queue(self):
        return await self._read_file(self.player_queue_file)
    
    async def restore_queue(self, queue):
        await self._write_file(self.player_queue_file, queue)
        
    
        