import itertools
import sys
from collections import namedtuple
from threading import Thread

import networkx as nx
import numpy as np
import pygame
from pygame import gfxdraw

from TickTacToe.games import alpha_beta_player

# Game constants
BOARD_BROWN = (199, 105, 42)
BOARD_WIDTH = 700
BOARD_BORDER = 75
STONE_RADIUS = 14
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
TURN_POS = (BOARD_BORDER, 20)
SCORE_POS = (BOARD_BORDER, BOARD_WIDTH - BOARD_BORDER + 30)
DOT_RADIUS = 4

PLAYER_BLACK = 1
PLAYER_WHITE = 2

GameState = namedtuple('GameState', 'to_move, utility, board, moves, branching')


def make_grid(size):
    """Return list of (start_point, end_point pairs) defining gridlines
    Args:
        size (int): size of grid
    Returns:
        Tuple[List[Tuple[float, float]]]: start and end points for gridlines
    """
    start_points, end_points = [], []

    # vertical start points (constant y)
    xs = np.linspace(BOARD_BORDER, BOARD_WIDTH - BOARD_BORDER, size)
    ys = np.full((size), BOARD_BORDER)
    start_points += list(zip(xs, ys))

    # horizontal start points (constant x)
    xs = np.full((size), BOARD_BORDER)
    ys = np.linspace(BOARD_BORDER, BOARD_WIDTH - BOARD_BORDER, size)
    start_points += list(zip(xs, ys))

    # vertical end points (constant y)
    xs = np.linspace(BOARD_BORDER, BOARD_WIDTH - BOARD_BORDER, size)
    ys = np.full((size), BOARD_WIDTH - BOARD_BORDER)
    end_points += list(zip(xs, ys))

    # horizontal end points (constant x)
    xs = np.full((size), BOARD_WIDTH - BOARD_BORDER)
    ys = np.linspace(BOARD_BORDER, BOARD_WIDTH - BOARD_BORDER, size)
    end_points += list(zip(xs, ys))

    return (start_points, end_points)


def xy_to_colrow(x, y, size):
    """Convert x,y coordinates to column and row number
    Args:
        x (float): x position
        y (float): y position
        size (int): size of grid
    Returns:
        Tuple[int, int]: column and row numbers of intersection
    """
    inc = (BOARD_WIDTH - 2 * BOARD_BORDER) / (size - 1)
    x_dist = x - BOARD_BORDER
    y_dist = y - BOARD_BORDER
    col = int(round(x_dist / inc))
    row = int(round(y_dist / inc))
    return col, row


def colrow_to_xy(col, row, size):
    """Convert column and row numbers to x,y coordinates
    Args:
        col (int): column number (horizontal position)
        row (int): row number (vertical position)
        size (int): size of grid
    Returns:
        Tuple[float, float]: x,y coordinates of intersection
    """
    inc = (BOARD_WIDTH - 2 * BOARD_BORDER) / (size - 1)
    x = int(BOARD_BORDER + col * inc)
    y = int(BOARD_BORDER + row * inc)
    return x, y


def is_valid_move(col, row, board):
    """Check if placing a stone at (col, row) is valid on board
    Args:
        col (int): column number
        row (int): row number
        board (object): board grid (size * size matrix)
    Returns:
        boolean: True if move is valid, False otherewise
    """
    # TODO: check for ko situation (infinite back and forth)
    if col < 0 or col >= board.shape[0]:
        return False
    if row < 0 or row >= board.shape[0]:
        return False
    return board[col, row] == 0


# Actualy not used
def has_no_liberties(board, group):
    """Check if a stone group has any liberties on a given board.
    Args:
        board (object): game board (size * size matrix)
        group (List[Tuple[int, int]]): list of (col,row) pairs defining a stone group
    Returns:
        [boolean]: True if group has any liberties, False otherwise
    """
    for x, y in group:
        if x > 0 and board[x - 1, y] == 0:
            return False
        if y > 0 and board[x, y - 1] == 0:
            return False
        if x < board.shape[0] - 1 and board[x + 1, y] == 0:
            return False
        if y < board.shape[0] - 1 and board[x, y + 1] == 0:
            return False
    return True


# Actualy not used
def get_stone_groups(board, color):
    """Get stone groups of a given color on a given board
    Args:
        board (object): game board (size * size matrix)
        color (str): name of color to get groups for
    Returns:
        List[List[Tuple[int, int]]]: list of list of (col, row) pairs, each defining a group
    """
    size = board.shape[0]
    color_code = PLAYER_BLACK if color == "black" else PLAYER_WHITE
    xs, ys = np.where(board == color_code)
    graph = nx.grid_graph(dim=[size, size])
    stones = set(zip(xs, ys))
    all_spaces = set(itertools.product(range(size), range(size)))
    stones_to_remove = all_spaces - stones
    graph.remove_nodes_from(stones_to_remove)
    return nx.connected_components(graph)


class Gomoku:
    def __init__(self, size, k=5):

        self.k = k

        # Where the game is getting involved
        self.x_min = 16
        self.x_max = -1
        self.y_min = 16
        self.y_max = -1

        self.board = np.zeros((size, size))
        self.size = size
        self.black_turn = True
        self.start_points, self.end_points = make_grid(self.size)

        moves = [(x, y) for x in range(size)
                 for y in range(size)]

        self.initial = GameState(to_move=PLAYER_BLACK, utility=0, board=self.board, moves=moves, branching=2)

    def init_pygame(self):
        # Inizializza la partita
        pygame.init()
        screen = pygame.display.set_mode((BOARD_WIDTH, BOARD_WIDTH))
        self.screen = screen
        self.ZOINK = pygame.mixer.Sound("wav/zoink.wav")
        self.CLICK = pygame.mixer.Sound("wav/click.wav")
        self.font = pygame.font.SysFont("arial", 30)

    def actions(self, state):
        """Legal moves are any square not yet taken."""
        return state.moves

    def result(self, state, move):
        if move not in state.moves:
            return state  # Illegal move has no effect
        board = state.board.copy()

        board[move] = state.to_move

        moves = self.compute_moves(board)
        return GameState(to_move=(PLAYER_WHITE if state.to_move == PLAYER_BLACK else PLAYER_BLACK),
                         utility=self.compute_utility(board, move, state.to_move),
                         board=board,
                         moves=moves,
                         branching=state.branching - 1)

    def utility(self, state, player):
        """Return the value to player; 1 for win, -1 for loss, 0 otherwise."""
        return state.utility if player == PLAYER_BLACK else -state.utility

    def terminal_test(self, state):
        """A state is terminal if it is won or there are no empty squares."""
        return state.utility != 0 or len(state.moves) == 0 or state.branching == 0

    def display(self, state):
        board = state.board
        for x in range(1, self.size + 1):
            for y in range(1, self.size + 1):
                print(board.get((x, y), '.'), end=' ')
            print()

    def draw(self):
        # draw stones - filled circle and antialiased ring
        self.clear_screen()
        for col, row in zip(*np.where(self.board == 1)):
            x, y = colrow_to_xy(col, row, self.size)
            gfxdraw.aacircle(self.screen, x, y, STONE_RADIUS, BLACK)
            gfxdraw.filled_circle(self.screen, x, y, STONE_RADIUS, BLACK)
        for col, row in zip(*np.where(self.board == 2)):
            x, y = colrow_to_xy(col, row, self.size)
            gfxdraw.aacircle(self.screen, x, y, STONE_RADIUS, WHITE)
            gfxdraw.filled_circle(self.screen, x, y, STONE_RADIUS, WHITE)

        turn_msg = (
                f"{'Black' if self.black_turn else 'White'} to move. "
                + "Click to place stone, press P to pass."
        )
        txt = self.font.render(turn_msg, True, BLACK)
        self.screen.blit(txt, TURN_POS)

        pygame.display.flip()

    def update(self):
        events = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_p:
                    self.pass_move()
                    self.bot_move()

        if len(events) > 0:
            if events[0].type == pygame.MOUSEBUTTONUP and self.black_turn:
                self.handle_click()

    def extract_arrays(self, board):
        diag = []
        transpose_board = np.transpose(board)
        flipped_board = np.flip(board, 1)
        flipped_transposed = np.transpose(flipped_board)

        rows = [board[_, :] for _ in range(board.shape[0])]
        cols = [board[:, _] for _ in range(board.shape[1])]

        # Extract all diagonals
        for j in range(self.size - self.k + 1):
            if j + self.k <= self.size:
                diag.append(np.diag(board[0:, j:]))
                diag.append(np.diag(flipped_board[0:, j:]))
                if j != 0:
                    diag.append(np.diag(transpose_board[0:, j:]))
                    diag.append(np.diag(flipped_transposed[0:, j:]))

        return [*rows, *cols, *diag]

    def compute_utility(self, board, move, player):
        """If 'X' wins with this move, return 1; if 'O' wins return -1; else return 0."""
        arrays = self.extract_arrays(board)
        score = 0
        for array in arrays:
            score += self.evaluate_line(array)
        return score

    def evaluate_line(self, array):

        res = {}
        # t_fiveInRow = Thread(target=self.checkFiveInRow, args=(array, res))
        # t_fourInRow = Thread(target=self.checkFourInRow, args=(array, res))
        # t_brokenFour = Thread(target=self.checkBrokenFour, args=(array, res))
        # t_threeInRow = Thread(target=self.checkThreeInRow, args=(array, res))
        # t_brokenThree = Thread(target=self.checkBrokenThree, args=(array, res))
        #
        # t_fiveInRow.start()
        # t_fourInRow.start()
        # t_brokenFour.start()
        # t_threeInRow.start()
        # t_brokenThree.start()
        #
        # t_fiveInRow.join()
        # t_fourInRow.join()
        # t_brokenFour.join()
        # t_threeInRow.join()
        # t_brokenThree.join()

        self.checkFiveInRow(array, res)
        self.checkFourInRow(array, res)
        self.checkBrokenFour(array, res)
        self.checkThreeInRow(array, res)
        self.checkBrokenThree(array, res)

        return 1000 * res["FiveInRow"] + \
               300 * res["FourInRow"] + \
               200 * res["BrokenFour"] + \
               75 * res["ThreeInRow"] + \
               60 * res["BrokenThree"]

    def subarray(self, array, length_subarray):
        return np.fromfunction(lambda i, j: array[i + j], (len(array) - length_subarray + 1, length_subarray),
                               dtype=int)

    def checkFiveInRow(self, array, res):
        lines = self.subarray(array, 5)
        count = 0
        for line in lines:
            if np.all(line == [1, 1, 1, 1, 1]):
                count += 1
        res["FiveInRow"] = count

    def checkFourInRow(self, array, res):
        lines = self.subarray(array, 5)
        count = 0
        for line in lines:
            if np.all(line == [0, 1, 1, 1, 1]) or \
                    np.all(line == [1, 1, 1, 1, 0]):
                count += 1
        res["FourInRow"] = count

    def checkBrokenFour(self, array, res):
        lines = self.subarray(array, 5)
        count = 0
        for line in lines:
            if np.all(line == [1, 1, 0, 1, 1]) or \
                    np.all(line == [1, 1, 1, 0, 1]) or \
                    np.all(line == [1, 0, 1, 1, 1]):
                count += 1
        res["BrokenFour"] = count

    def checkThreeInRow(self, array, res):
        lines = self.subarray(array, 5)
        count = 0
        for line in lines:
            if np.all(line == [0, 1, 1, 1, 0]) or \
                    np.all(line == [1, 1, 1, 0, 0]) or \
                    np.all(line == [0, 0, 1, 1, 1]):
                count += 1
        res["ThreeInRow"] = count

    def checkBrokenThree(self, array, res):
        lines = self.subarray(array, 5)
        count = 0
        for line in lines:
            if np.all(line == [0, 1, 0, 1, 1]) or \
                    np.all(line == [0, 1, 1, 0, 1]) or \
                    np.all(line == [1, 1, 0, 1, 0]) or \
                    np.all(line == [1, 0, 1, 1, 0]):
                count += 1
        res["BrokenThree"] = count

    def clear_screen(self):

        # fill board and add gridlines
        self.screen.fill(BOARD_BROWN)
        for start_point, end_point in zip(self.start_points, self.end_points):
            pygame.draw.line(self.screen, BLACK, start_point, end_point)

        # add guide dots
        guide_dots = [3, self.size // 2, self.size - 4]
        for col, row in itertools.product(guide_dots, guide_dots):
            x, y = colrow_to_xy(col, row, self.size)
            gfxdraw.aacircle(self.screen, x, y, DOT_RADIUS, BLACK)
            gfxdraw.filled_circle(self.screen, x, y, DOT_RADIUS, BLACK)

        pygame.display.flip()

    def update_game_range(self, x, y):
        if self.x_min > x:
            self.x_min = x
        if self.x_max < x:
            self.x_max = x
        if self.y_min > y:
            self.y_min = y
        if self.y_max < y:
            self.y_max = y

    def pass_move(self):
        self.black_turn = not self.black_turn
        self.draw()

    def to_move(self, state):
        return PLAYER_WHITE

    def bot_move(self):
        # BOT move
        state = GameState(to_move=PLAYER_WHITE,
                          utility=0,
                          board=self.board,
                          moves=self.compute_moves(self.board),
                          branching=3)
        col_bot, row_bot = alpha_beta_player(game, state)

        # range game coordinates
        self.update_game_range(col_bot, row_bot)

        # draw stone, play sound, check end and pass move
        self.board[col_bot, row_bot] = PLAYER_WHITE
        self.CLICK.play()
        self.end(PLAYER_WHITE, (col_bot, row_bot))
        self.pass_move()

    def handle_click(self):
        # get board position
        x, y = pygame.mouse.get_pos()
        col, row = xy_to_colrow(x, y, self.size)
        if not is_valid_move(col, row, self.board):
            self.ZOINK.play()
            return

        # range game coordinates
        self.update_game_range(col, row)

        # draw stone, play sound, check end and pass move
        self.board[col, row] = PLAYER_BLACK
        self.CLICK.play()
        self.end(PLAYER_BLACK, (col, row))
        self.pass_move()
        self.bot_move()

    def compute_moves(self, board):

        def filtering(position):
            x, y = position
            padded = np.pad(board, 1)

            if board[x][y] == 0:
                if np.any(padded[x:x + 3, y:y + 3] != 0):
                    return True
            else:
                return False

        return set(filter(filtering, [(x, y)
                                      for x in range(self.size)
                                      for y in range(self.size)]))

    def critical(self):
        pass

    def end(self, player, move):
        # Check ends of game
        x, y = move
        x = x + 5
        y = y + 5
        padded = np.pad(self.board, 5)

        row_tagliata = padded[x - 5:x + 6, y]
        col_tagliata = padded[x, y - 5:y + 6]
        diag = np.diag(padded[x - 5:x + 6, y - 5:y + 6])
        diag2 = np.diag(np.flip(padded[x - 5:x + 6, y - 5:y + 6], 1))

        count = 0
        for l in [col_tagliata, row_tagliata, diag, diag2]:
            for elem in l:
                if elem == player:
                    count += 1
                elif count == 5:
                    break
                else:
                    count = 0

            if count == 5:
                self.win()
            else:
                count = 0

    def win(self):
        # TODO: Win
        exit(1)
        pass


if __name__ == "__main__":
    game = Gomoku(15)
    game.init_pygame()

    while True:
        game.draw()
        game.update()
        pygame.time.wait(100)
