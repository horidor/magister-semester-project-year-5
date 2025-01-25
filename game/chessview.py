import pygame
import chess

class ChessView:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 800))
        pygame.display.set_caption("Chess Multiplayer with Elo")
        self.font = pygame.font.Font(None, 50)
        self.piece_sprites = pygame.image.load("resources/chess_pieces.png")

    def draw_text(self, text, position, color=(255, 255, 255)):
        rendered_text = self.font.render(text, True, color)
        self.screen.blit(rendered_text, position)
        
    def draw_button(self, text, button_rect, color, hover_color, is_hovered):
        """Draw a button with hover effect."""
        rect_color = hover_color if is_hovered else color
        pygame.draw.rect(self.screen, rect_color, button_rect)
        text_surface = self.font.render(text, True, (0, 0, 0))
        text_rect = text_surface.get_rect(center=button_rect.center)
        self.screen.blit(text_surface, text_rect)
        return button_rect

    def draw_board(self, board_state, legal_moves=None, selected_square=None):
        """Draw the chessboard and pieces."""
        self.screen.fill((0, 0, 0))
        for x in range(8):
            for y in range(8):
                rect = pygame.Rect(x * 100, y * 100, 100, 100)
                color = (118, 150, 86) if (x + y) % 2 else (238, 238, 210)
                pygame.draw.rect(self.screen, color, rect)

                # Highlight selected square
                if selected_square == chess.square(x, 7 - y):
                    pygame.draw.rect(self.screen, (0, 255, 0), rect, 5)

                # Highlight legal moves
                if legal_moves and chess.square(x, 7 - y) in legal_moves:
                    pygame.draw.circle(self.screen, (0, 0, 255), rect.center, 15)

                # Draw pieces from the board state
                piece = board_state.piece_at(chess.square(x, 7 - y))
                if piece:
                    self._draw_piece(piece, x, y)

        pygame.display.flip()

    def _draw_piece(self, piece, x, y):
        """Draw a chess piece at the given board position."""
        piece_type = piece.piece_type
        color_offset = 1 if piece.color == chess.WHITE else 0  # White on top, black on bottom
        piece_offset = 6 - piece_type
        sprite_rect = pygame.Rect(piece_offset * 60, color_offset * 60, 60, 60)
        self.screen.blit(self.piece_sprites, (x * 100 + 20, y * 100 + 20), sprite_rect)

    def draw_login_screen(self, username, password, input_active, error_message, mouse_pos):
        self.screen.fill((0, 0, 0))
        self.draw_text("Chess Multiplayer", (250, 50))
        self.draw_text("Username:", (150, 200))
        self.draw_text(username, (400, 200), (255, 255, 255) if input_active == "username" else (150, 150, 150))
        self.draw_text("Password:", (150, 300))
        self.draw_text("*" * len(password), (400, 300), (255, 255, 255) if input_active == "password" else (150, 150, 150))
        
        
        auth_button_pos = pygame.Rect(150, 400, 200, 50)
        register_button_pos = pygame.Rect(400, 400, 200, 50)
        authorize_button = self.draw_button("Authorize", auth_button_pos, (100, 200, 100), (150, 255, 150), auth_button_pos.collidepoint(mouse_pos))
        register_button = self.draw_button("Register", register_button_pos, (100, 100, 200), (150, 150, 255), register_button_pos.collidepoint(mouse_pos))

        if error_message:
            self.draw_text(error_message, (150, 500), (255, 0, 0))

        pygame.display.flip()
        return authorize_button, register_button

    def draw_menu_screen(self, username, elo, mouse_pos):
        self.screen.fill((0, 0, 0))
        self.draw_text(f"Welcome, {username}!", (250, 50))
        self.draw_text(f"Elo: {elo}", (250, 150))
        start_button_pos = pygame.Rect(250,300,300,50)
        logout_button_pos= pygame.Rect(250,400,300,50)

        start_button = self.draw_button("Find Game", start_button_pos, (0, 128, 0), (0, 200, 0), start_button_pos.collidepoint(mouse_pos))
        logout_button = self.draw_button("Logout", logout_button_pos, (128, 0, 0), (200, 0, 0), logout_button_pos.collidepoint(mouse_pos))
        pygame.display.flip()
        return start_button, logout_button
    
    def wrap_text(self, text, max_width):
        words = text.split(' ')
        wrapped_lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            if self.font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                wrapped_lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            wrapped_lines.append(' '.join(current_line))

        return wrapped_lines

    def draw_message_screen(self, message):
        self.screen.fill((0, 0, 0))
        wrapped_lines = self.wrap_text(message, self.screen.get_width() - 20)  
    
        y_offset = 100  
        line_height = self.font.size("A")[1]  

        for line in wrapped_lines:
            self.draw_text(line, (self.screen.get_width() // 2, y_offset), (255, 255, 255))
            y_offset += line_height + 5  
            
        pygame.display.flip()
        

    def draw_waiting_screen(self):
        self.screen.fill((0, 0, 0))
        self.draw_text("Waiting for an opponent...", (200, 400), (255, 255, 255))
        pygame.display.flip()