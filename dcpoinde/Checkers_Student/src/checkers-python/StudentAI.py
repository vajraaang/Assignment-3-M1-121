from random import randint
from BoardClasses import Move
from BoardClasses import Board
from Checker import Checker
from math import sqrt, log
from copy import deepcopy as dc
#The following part should be completed by students.
#Students can modify anything except the class name and exisiting functions and varibles.
class StudentAI():
    def __init__(self,col,row,p):
        self.col = col
        self.row = row
        self.p = p
        self.board = Board(col,row,p)
        self.board.initialize_game()
        self.color = ''
        self.opponent = {1:2,2:1}
        self.color = 2

        self.move_tree = None

    def get_move(self,move):
        if len(move) != 0:
            self.board.make_move(move, self.opponent[self.color])

            if self.move_tree is not None: 
                for child in self.move_tree.children:
                    if child.move_taken.seq == move.seq:
                        self.move_tree = child
                
        else:
            self.color = 1

        if (self.move_tree is None) or ((self.move_tree.move_taken is not None) and (self.move_tree.move_taken.seq != move.seq)):
            self.simulate()
        
        self.color = self.move_tree.turn
        child = self.move_tree.calculate_best_choice()

        if child == -1:
            """
            No child returned, revert to random choice
            """
            moves = self.board.get_all_possible_moves(self.color)
            index = randint(0, len(moves) - 1)
            inner_index = randint(0, len(moves[index]) - 1)
            move = moves[index][inner_index]
            self.board.make_move(move, self.color)
        else:
            move = child.move_taken

            self.board.make_move(move, self.color)
            self.move_tree = child

        return move

    def simulate(self):
        root = MoveTree(self.color, False, False, False, False, False, False)
        
        for i in range(0, 500):
            board = dc(self.board)
            node = root
            sim_turn = self.color
            """
            Generate the simulation tree
            """
            while board.is_win(sim_turn) == 0:
                piece_count = board.black_count + board.white_count
                moves = board.get_all_possible_moves(sim_turn)

                if len(moves) == 0:
                    break

                move = self.choose_move(board, sim_turn)
                board.make_move(move, sim_turn)

                if sim_turn == 1:
                    sim_turn = 2
                else:
                    sim_turn = 1

                updated = False
                for child in node.children:
                    if child.move_taken.seq == move.seq:
                        node = child
                        updated = True
                        break

                if not updated:
                    makes_king = False
                    if not board.board[move.seq[0][0]][move.seq[0][1]].is_king and board.board[move.seq[-1][0]][move.seq[-1][1]].is_king:
                        makes_king = True

                    takes = False
                    if board.white_count + board.black_count < piece_count:
                        takes = True

                    danger = False
                    for piece in board.get_all_possible_moves(sim_turn):
                        for mv in piece:
                            start = mv.seq[0]
                            target = mv.seq[1]
                            if abs(start[0] - target[0]) + abs(start[1] - target[1]) > 2:
                                danger = True
                                break

                    next_king = False
                    if not board.board[move.seq[-1][0]][move.seq[-1][1]].is_king and not makes_king and ((move.seq[-1][0] - 1 == 0 and self.color == 2) or (move.seq[-1][0] + 1 == self.row - 1 and self.color == 1)):
                        next_king = True

                    center = False
                    if move.seq[-1][0] in range((self.row // 2) - 2, (self.row // 2) + 2) and move.seq[-1][1] in range((self.col // 2) - 2, (self.col // 2) + 2):
                        center = True

                    out = False
                    if node.danger < 0 and not danger:
                        out = True
                    
                    node = node.add_new_state(sim_turn, makes_king, takes, danger, next_king, center, out, move)

            """
            Backtrack through the tree applying the result of the game
            """
            winner = board.is_win(sim_turn)
            while node is not None:
                node.simulations += 1
                if node.turn == winner:
                    node.wins += 1
                elif winner == -1 or winner == 0:
                    node.wins += 0.5
                node = node.parent

        self.move_tree = root
    
    def choose_move(self, board, turn):
        moves = board.get_all_possible_moves(turn)
        scores = []

        for piece in moves:
            for mv in piece:
                start = mv.seq[0]
                target = mv.seq[-1]
                score = 0

                if not board.board[start[0]][start[1]].is_king and ((target[0] == self.row - 1 and turn == 1) or (target[0] == 0 and turn == 2)):
                    score += 3

                if abs(start[0] - target[0]) + abs(start[1] - target[1]) > 2:
                    score += 2

                if target[0] in range((self.row // 2) - 2, (self.row // 2) + 2) and target[1] in range((self.col // 2) - 2, (self.col // 2) + 2):
                    score += 0.5

                scores.append((score, mv))
        
        best = []
        scores.sort(key=lambda x: x[0], reverse=True)
        for sc, m in scores:
            if scores[0][0] == 0:
                index = randint(0, len(scores) - 1)
                return scores[index][1]
            if sc == scores[-1][0]:
                best.append(m)
        
        random_best = randint(0, len(best) - 1)
        return best[random_best]


class MoveTree():
    def __init__(self, turn: int, makes_king: bool, takes: bool, danger: bool, next_king: bool, center: bool, out: bool, parent = None, move = None):
        self.turn = turn
        self.parent = parent
        self.move_taken = move

        self.children = []

        self.c = sqrt(2)
        self.wins = 0
        self.simulations = 0
        self.uct = 0

        self.king_bonus = 0
        if makes_king:
            self.king_bonus = 1.5

        self.takes = 0
        if takes:
            self.takes = 0.75 * (len(self.move_taken) - 1)

        self.danger = 0
        if danger:
            self.danger = -1.0

        self.next_king = 0
        if next_king:
            self.next_king = 0.4

        self.center = 0
        if center:
            self.center = 0.2

        self.out = 0
        if out:
            self.out = 0.6

        self.bonuses = self.king_bonus + self.takes + self.danger + self.next_king + self.center + self.out

    def add_new_state(self, new_turn: int, makes_king: bool, takes: bool, danger: bool, next_king: bool, center: bool, out: bool, move_taken):
        new_node = MoveTree( 
            turn = new_turn, 
            makes_king = makes_king,
            takes = takes,
            danger = danger,
            next_king = next_king,
            center = center,
            out = out,
            parent = self, 
            move = move_taken
        )

        self.children.append(new_node)
        return new_node

    def calculate_best_choice(self):
        if len(self.children) == 0:
            return -1

        for child in self.children:
            if child.simulations == 0:
                child
                continue
            
            child.uct = (child.wins / child.simulations 
                          + (child.c * sqrt(log(max(1, child.parent.simulations)) / child.simulations)) 
                          + child.bonuses
                        )

        return max(self.children, key=lambda x: x.uct)