import threading
import pygame
import chess
import sys

class ChessPresenter:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.username = ""
        self.password = ""
        self.elo = ""
        self.input_active = "username"
        self.error_message = None
        self.selected_square = None
        self.legal_moves = []
        self.state = "login"
        
        if not self.model.connect_to_server():
            self.view.draw_message_screen("Unable to connect to server. Try again or later.")
            self._exit_game()
            
    def _exit_game(self):
        pygame.time.wait(5000)
        pygame.quit()
        sys.exit()

    def _handle_server_message(self, message):
        print(message)
        if type(message) == "listen_error":
            self.view.draw_message_screen("Disconnect with server occured.")
            self._exit_game()
        
        if message["type"] == "opponent_disconnected":
            self.view.draw_message_screen("Opponent has disconnected.")
            pygame.time.wait(3000)
            self.model.color = None
            self.model.game_id = None
            self.state = "mainmenu"
        
        if message["type"] == "game_start":
            self.model.color = message["color"]
            self.model.game_id = message["game_id"]
            self.model.board = chess.Board(message["board"])
            self.state = "game"
            
        elif message["type"] == "update":
            move = chess.Move.from_uci(message["move"])
            self.model.make_move(move)
            
        elif message["type"] == "login_success":
            self.model.username = message["username"]
            self.username = message["username"]
            self.model.token = message["token"]
            self.state = "mainmenu"
            self.elo = message["elo"]
            
        elif message["type"] == "register_success":
            self.error_message = "Registration successful! Please log in."
            
        elif message["type"] == "game_end":
            if "winner" in message:
                if message["winner"] == self.model.color:
                    self.view.draw_message_screen("You have won!")
                elif message["winner"] == "draw":
                    self.view.draw_message_screen("Game has ended in a draw")
                else:
                    self.view.draw_message_screen("You have lost")
                self.elo = message["elo"]
            else:
                self.view.draw_message_screen("Unknown error interrupted your game.") 
                self.state = "mainmenu"
                
            pygame.time.wait(3000)
            self.state = "mainmenu"
                
        elif message["type"] == "server_shutdown":
            self.view.draw_message_screen("Server is shutting down.")
            self._exit_game()
            
        elif message["type"] == "conn_loss":
            self.view.draw_message_screen("Server connection lost.")
            self._exit_game()
            
        else:
            self.error_message = message.get("reason", "An error occurred.")
            
    def _handle_piece_selection(self, pos):
        x, y = pos[0] // 100, 7 - pos[1] // 100
        square = chess.square(x, y)
        piece = self.model.board.piece_at(square)

        if not self.selected_square:
            if piece and piece.color == (self.model.color == "white"):
                print("select")
                self.selected_square = square
                self.legal_moves = [
                    move.to_square for move in self.model.board.legal_moves if move.from_square == square
                ]
        else:
            move = chess.Move(self.selected_square, square)
            if move in self.model.board.legal_moves:
                self.model.send_to_server({"type": "move", "username": self.username, "game_id": self.model.game_id, "move": move.uci()})
            self.selected_square = None
            self.legal_moves = []  
  
  
        
    def main_loop(self):
        print("here!")
        while True:
            mouse_pos = pygame.mouse.get_pos()
            clock = pygame.time.Clock() 
            while True:
                message = self.model.get_response()
                if message == None:
                    break
                
                self._handle_server_message(message)
            
            if self.state == "login":
                self._login_registration(mouse_pos)
            elif self.state == "mainmenu":
                self._menu_loop(mouse_pos)
            elif self.state == "wait":
                self._waiting_loop()        
            elif self.state == "game":
                self._game_loop(clock)
            
    def _login_registration(self, mouse_pos):
        authorize_button, register_button = self.view.draw_login_screen(
            self.username, 
            self.password, 
            self.input_active, 
            self.error_message,
            mouse_pos
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._exit_game()
                
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.input_active = "password" if self.input_active == "username" else "username"
                    
                elif event.key == pygame.K_BACKSPACE:
                    if self.input_active == "username":
                        self.username = self.username[:-1]
                    else:
                        self.password = self.password[:-1]
                        
                else:
                    if self.input_active == "username":
                        self.username += event.unicode
                    else:
                        self.password += event.unicode
                        
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if authorize_button.collidepoint(mouse_pos):
                    self.error_message = ""
                    self.model.login(self.username, self.password)
                    self.password = ""
                elif register_button.collidepoint(mouse_pos):
                    self.error_message = ""
                    self.model.register(self.username, self.password)
                    self.username = ""
                    self.password = ""
                            
    
    def _waiting_loop(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._exit_game()
                
        self.view.draw_waiting_screen()
    
    def _menu_loop(self, mouse_pos):
        elo = self.elo

        start_button, logout_button = self.view.draw_menu_screen(
                self.model.username,
                elo,
                mouse_pos
            )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._exit_game()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_button.collidepoint(mouse_pos):
                    self.model.find_game()
                    self.state = "wait"
                elif logout_button.collidepoint(mouse_pos):
                    self.model.logout()
                    self.username = ""
                    self.state = "login"
                    

    def _game_loop(self, clock):
        clock = pygame.time.Clock()

        self.view.draw_board(self.model.board, self.legal_moves, self.selected_square)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._exit_game()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self._handle_piece_selection(event.pos)
            
        self.view.draw_board(self.model.board, self.legal_moves, self.selected_square)

        clock.tick(60)


