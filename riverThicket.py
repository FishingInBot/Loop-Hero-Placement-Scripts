#!/usr/bin/env python3
import random, math, time, tkinter as tk
from tkinter import messagebox

# Grid dimensions
WIDTH = 21
HEIGHT = 12

# Global active mask:
#   True means the cell is available (active) for use,
#   False means the cell is unavailable (user–selected).
active_mask = [[True for _ in range(WIDTH)] for _ in range(HEIGHT)]


####################################
# UI for Selecting Active Cells
####################################
class CellSelector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Select Active Cells")
        self.buttons = {}
        # Create a grid of buttons
        for i in range(HEIGHT):
            for j in range(WIDTH):
                btn = tk.Button(self, width=2, height=1,
                                command=lambda i=i, j=j: self.toggle_cell(i, j))
                btn.grid(row=i, column=j, padx=1, pady=1)
                self.buttons[(i, j)] = btn
                btn.config(bg="white")
        # Add a Start button below the grid
        self.start_button = tk.Button(self, text="Start Optimization", command=self.on_start)
        self.start_button.grid(row=HEIGHT, column=0, columnspan=WIDTH, sticky="we")
        self.selected = False

    def toggle_cell(self, i, j):
        global active_mask
        # Toggle the state
        active_mask[i][j] = not active_mask[i][j]
        btn = self.buttons[(i, j)]
        if active_mask[i][j]:
            btn.config(bg="white")
        else:
            btn.config(bg="gray")

    def on_start(self):
        # Make sure at least one cell is active.
        if not any(active_mask[i][j] for i in range(HEIGHT) for j in range(WIDTH)):
            messagebox.showerror("Error", "No active cells selected!")
            return
        self.selected = True
        self.destroy()

def run_selection():
    app = CellSelector()
    app.mainloop()


####################################
# Optimization and Utility Functions
####################################
def in_bounds(i, j):
    return 0 <= i < HEIGHT and 0 <= j < WIDTH

def neighbors(i, j):
    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ni, nj = i + di, j + dj
        if in_bounds(ni, nj):
            yield ni, nj

def init_layout():
    """
    Build a layout grid based on the active mask.
    Active cells become thickets ('T'); inactive cells are marked 'I'.
    """
    layout = []
    for i in range(HEIGHT):
        row = []
        for j in range(WIDTH):
            if active_mask[i][j]:
                row.append('T')
            else:
                row.append('I')
        layout.append(row)
    return layout

def count_river_neighbors(i, j, layout):
    """Count adjacent cells that are rivers ('R')."""
    return sum(1 for ni, nj in neighbors(i, j) if layout[ni][nj] == 'R')

def cell_score(i, j, layout):
    """
    A thicket cell ('T') scores 2 * 2^(# of adjacent river cells).
    River cells and inactive cells score 0.
    """
    if layout[i][j] != 'T':
        return 0
    r = count_river_neighbors(i, j, layout)
    return 2 * (2 ** r)

def total_score(layout):
    return sum(cell_score(i, j, layout) for i in range(HEIGHT) for j in range(WIDTH))

def snake_to_layout(snake):
    """
    Given a snake (list of (i,j) cells), mark those active cells as river ('R')
    in the layout and return the layout.
    """
    layout = init_layout()
    for (i, j) in snake:
        if active_mask[i][j]:
            layout[i][j] = 'R'
    return layout

def is_extension_candidate(pos, head, snake_set):
    """
    For candidate cell pos (i,j) to be an extension of the snake:
      - It must be active.
      - It must not already be in the snake.
      - It must be adjacent to the current head.
      - It must not touch any other snake cell (to avoid self-intersection).
    """
    i, j = pos
    if pos in snake_set:
        return False
    if not active_mask[i][j]:
        return False
    hi, hj = head
    if abs(i - hi) + abs(j - hj) != 1:
        return False
    for ni, nj in neighbors(i, j):
        if (ni, nj) in snake_set and (ni, nj) != head:
            return False
    return True

def random_regrow(snake, trunc_index):
    """
    Truncate the snake at trunc_index and regrow it randomly (if possible)
    while obeying the non–self–intersection rule.
    """
    new_snake = snake[:trunc_index+1]
    snake_set = set(new_snake)
    head = new_snake[-1]
    max_steps = 200  # safeguard
    steps = 0
    while steps < max_steps:
        candidates = []
        for ni, nj in neighbors(*head):
            pos = (ni, nj)
            if is_extension_candidate(pos, head, snake_set):
                candidates.append(pos)
        if not candidates:
            break  # no legal extension available
        next_cell = random.choice(candidates)
        new_snake.append(next_cell)
        snake_set.add(next_cell)
        head = next_cell
        steps += 1
    return new_snake

def simulated_annealing(initial_snake, time_limit=120):
    """
    Use simulated annealing to search for a better snake layout.
    Moves consist of randomly truncating the snake and regrowing it.
    We now exit early if the temperature falls below 1.0.
    """
    current_snake = initial_snake
    current_layout = snake_to_layout(current_snake)
    current_score = total_score(current_layout)
    best_snake = current_snake
    best_score = current_score

    start_time = time.time()
    iteration = 0
    T0 = 100.0
    T_end = 0.1
    total_iterations = 100000  # nominal max iterations

    while time.time() - start_time < time_limit:
        iteration += 1
        frac = min(1.0, iteration / total_iterations)
        T = T0 * (1 - frac) + T_end * frac

        # Terminate early if temperature falls to or below 1.0.
        if T <= 1.0:
            print("Temperature threshold reached. Stopping optimization.")
            break

        if len(current_snake) <= 1:
            break

        trunc_index = random.randint(0, len(current_snake) - 1)
        candidate_snake = random_regrow(current_snake, trunc_index)
        candidate_layout = snake_to_layout(candidate_snake)
        candidate_score = total_score(candidate_layout)
        delta = candidate_score - current_score

        # Accept improvements or sometimes worse moves.
        if delta >= 0 or random.random() < math.exp(delta / T):
            current_snake = candidate_snake
            current_score = candidate_score
            if candidate_score > best_score:
                best_snake = candidate_snake
                best_score = candidate_score

        if iteration % 1000 == 0:
            print(f"Iteration {iteration:6d} | Current score: {current_score:6d} | "
                  f"Best score: {best_score:6d} | Temperature: {T:6.2f}")
    return best_snake, best_score


####################################
# Display Final Layout
####################################
def display_layout(layout):
    """
    Display the final layout in a new Tkinter window:
      - River cells: Soft blue (SkyBlue)
      - Active thicket cells: Soft green (PaleGreen)
      - Inactive cells: Light gray
    We remove text labels to keep the display clean.
    """
    window = tk.Tk()
    window.title("Final Layout")
    for i in range(HEIGHT):
        for j in range(WIDTH):
            cell = layout[i][j]
            if cell == 'R':
                bg = "SkyBlue"   # softer blue for river
            elif cell == 'T':
                bg = "PaleGreen" # softer green for thickets
            else:  # Inactive
                bg = "LightGray"
            label = tk.Label(window, text="", width=2, height=1,
                             bg=bg, relief="flat", borderwidth=1)
            label.grid(row=i, column=j, padx=1, pady=1)
    window.mainloop()

####################################
# Main
####################################
def main():
    # Run the UI for cell selection.
    run_selection()
    # After the selection window closes, active_mask reflects your choices.
    
    # Choose a starting border cell that is active.
    start = None
    # Try top border:
    for j in range(WIDTH):
        if active_mask[0][j]:
            start = (0, j)
            break
    if start is None:
        # Try bottom border:
        for j in range(WIDTH):
            if active_mask[HEIGHT-1][j]:
                start = (HEIGHT-1, j)
                break
    if start is None:
        # Try left border:
        for i in range(HEIGHT):
            if active_mask[i][0]:
                start = (i, 0)
                break
    if start is None:
        # Try right border:
        for i in range(HEIGHT):
            if active_mask[i][WIDTH-1]:
                start = (i, WIDTH-1)
                break
    if start is None:
        messagebox.showerror("Error", "No active border cell available for starting the river!")
        return

    # Generate an initial snake starting at the chosen border cell.
    initial_snake = [start]
    initial_snake = random_regrow(initial_snake, 0)
    initial_layout = snake_to_layout(initial_snake)
    initial_score = total_score(initial_layout)
    print("Initial snake length:", len(initial_snake), "Score:", initial_score)

    # Run simulated annealing (this might take a couple minutes).
    best_snake, best_score = simulated_annealing(initial_snake, time_limit=120)
    best_layout = snake_to_layout(best_snake)
    print("Best snake length:", len(best_snake), "Best score:", best_score)

    attackSpeed = 0

    # For each thicket, calculate the attack speed it gives.
    # 2 base, 2^# of adjacent river cells
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if best_layout[i][j] == 'T':
                attackSpeed += 2 * (2 ** count_river_neighbors(i, j, best_layout))

    # Display the stats this layout gives.
    print(f"Attack speed = {}")

    # Display the final layout.
    display_layout(best_layout)

if __name__ == '__main__':
    main()
