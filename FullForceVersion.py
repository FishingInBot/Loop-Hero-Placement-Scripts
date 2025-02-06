import tkinter as tk
from tkinter import messagebox
import random, math, time, copy

# Grid dimensions
WIDTH = 21
HEIGHT = 12

# Other constants
MAX_OASIS = 50

# Global active mask:
#   True means the cell is active (available), False means inactive.
active_mask = [[True for _ in range(WIDTH)] for _ in range(HEIGHT)]

# UI for Selecting Active Cells
class CellSelector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Select Active Cells")
        self.buttons = {}
        for i in range(HEIGHT):
            for j in range(WIDTH):
                btn = tk.Button(self, width=2, height=1,
                                command=lambda i=i, j=j: self.toggle_cell(i, j))
                btn.grid(row=i, column=j, padx=1, pady=1)
                self.buttons[(i, j)] = btn
                btn.config(bg="white")
        self.start_button = tk.Button(self, text="Start Optimization", command=self.on_start)
        self.start_button.grid(row=HEIGHT, column=0, columnspan=WIDTH, sticky="we")
        self.selected = False

    def toggle_cell(self, i, j):
        global active_mask
        active_mask[i][j] = not active_mask[i][j]
        btn = self.buttons[(i, j)]
        btn.config(bg="white" if active_mask[i][j] else "gray")

    def on_start(self):
        if not any(active_mask[i][j] for i in range(HEIGHT) for j in range(WIDTH)):
            messagebox.showerror("Error", "No active cells selected!")
            return
        self.selected = True
        self.destroy()

def run_selection():
    app = CellSelector()
    app.mainloop()
    
# Grid Utility Functions
def in_bounds(i, j):
    return 0 <= i < HEIGHT and 0 <= j < WIDTH

def neighbors(i, j):
    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ni, nj = i + di, j + dj
        if in_bounds(ni, nj):
            yield ni, nj

# State Representation
# Our state is a tuple: (snake, dessert_mask)
# - snake: a list of (i,j) coordinates representing a contiguous snake (all cells are rivers).
# - dessert_mask: a 2D list (HEIGHT x WIDTH) of booleans.
def init_dessert_mask():
    return [[False for _ in range(WIDTH)] for _ in range(HEIGHT)]

def choose_start():
    """
    Choose a starting active border cell.
    Preference: far left or far right side (avoiding corners).
    If none available, choose any active border cell.
    """
    candidates = []
    # Left border (j=0), avoid top and bottom corners.
    for i in range(1, HEIGHT-1):
        if active_mask[i][0]:
            candidates.append((i, 0))
    # Right border (j=WIDTH-1)
    for i in range(1, HEIGHT-1):
        if active_mask[i][WIDTH-1]:
            candidates.append((i, WIDTH-1))
    if candidates:
        return random.choice(candidates)
    # Otherwise, try top border (avoid corners) and bottom border.
    for j in range(1, WIDTH-1):
        if active_mask[0][j]:
            candidates.append((0, j))
        if active_mask[HEIGHT-1][j]:
            candidates.append((HEIGHT-1, j))
    if candidates:
        return random.choice(candidates)
    # Fallback: any active border cell.
    for i in range(HEIGHT):
        if active_mask[i][0]:
            return (i, 0)
        if active_mask[i][WIDTH-1]:
            return (i, WIDTH-1)
    for j in range(WIDTH):
        if active_mask[0][j]:
            return (0, j)
        if active_mask[HEIGHT-1][j]:
            return (HEIGHT-1, j)
    return None  # Should not happen if at least one active cell exists

def state_to_layout(state):
    """
    Given state = (snake, dessert_mask):
      - Cells in the snake are marked 'R'
      - Active cells not in the snake:
           if dessert_mask is True AND the cell is adjacent to a snake cell, mark as 'D'
           else mark as 'T'
      - Inactive cells are marked 'I'
    """
    snake_set = set(state[0])
    layout = []
    for i in range(HEIGHT):
        row = []
        for j in range(WIDTH):
            if not active_mask[i][j]:
                row.append('I')
            elif (i, j) in snake_set:
                row.append('R')
            elif state[1][i][j] and any((ni, nj) in snake_set for ni, nj in neighbors(i, j)):
                row.append('D')
            else:
                row.append('T')
        row = list(row)
        layout.append(row)
    return layout

# Scoring Functions
def total_score_layout(layout):
    """
    Total score is the sum of:
      - Thicket bonus: For each thicket ('T'), bonus = 2 * 2^(# adjacent snake cells).
      - Oasis bonus: For each snake cell (always 'R') that is adjacent to at least one dessert ('D'),
                     count it as an oasis.
                       Global oasis bonus = 0.5 * min(oasis_count, MAX_OASIS)
    (Desserts themselves do nothing.)
    """
    score = 0.0
    # Thicket bonus:
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if layout[i][j] == 'T':
                count = 0
                for ni, nj in neighbors(i, j):
                    if layout[ni][nj] == 'R':
                        count += 1
                score += 2 * (2 ** count)
    # Oasis bonus:
    oasis_count = 0
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if layout[i][j] == 'R':
                if any(layout[ni][nj] == 'D' for ni, nj in neighbors(i, j)):
                    oasis_count += 1
    score += 30 * min(oasis_count, MAX_OASIS)
    return score

def total_score_state(state):
    layout = state_to_layout(state)
    return total_score_layout(layout)

# Snake Moves (Connectivity Moves)
def random_regrow(snake, trunc_index):
    """
    Given a snake (list of (i,j)) and a truncation index,
    remove cells after trunc_index and regrow the snake randomly.
    Only active cells not already in the snake are allowed.
    The candidate must be adjacent to the current head and not adjacent
    to any snake cell except the current head.
    """
    new_snake = snake[:trunc_index+1]
    snake_set = set(new_snake)
    head_i, head_j = new_snake[-1]
    max_steps = 200  # safeguard
    steps = 0
    while steps < max_steps:
        candidates = []
        for ni, nj in neighbors(head_i, head_j):
            if not active_mask[ni][nj]:
                continue
            if (ni, nj) in snake_set:
                continue
            # Ensure candidate does not touch any snake cell except the current head.
            valid = True
            for xi, xj in neighbors(ni, nj):
                if (xi, xj) in snake_set and (xi, xj) != (head_i, head_j):
                    valid = False
                    break
            if valid:
                candidates.append((ni, nj))
        if not candidates:
            break
        next_cell = random.choice(candidates)
        new_snake.append(next_cell)
        snake_set.add(next_cell)
        head_i, head_j = next_cell
        steps += 1
    return new_snake

def snake_move(state):
    """
    Perform a snake move:
      - Randomly choose a truncation point in the snake and regrow the snake.
      - Clear any dessert marks from cells that become part of the snake.
    """
    current_snake, current_dessert = state
    if len(current_snake) <= 1:
        return state
    trunc_index = random.randint(0, len(current_snake) - 1)
    new_snake = random_regrow(current_snake, trunc_index)
    new_dessert = copy.deepcopy(current_dessert)
    # Clear dessert marks for cells now in the snake.
    for (i, j) in new_snake:
        new_dessert[i][j] = False
    return (new_snake, new_dessert)

# Dessert Moves
def dessert_move(state):
    """
    Perform a dessert move:
      - Choose a random active cell (not in the snake) that is adjacent to at least one snake cell.
      - Flip its dessert flag.
    """
    current_snake, current_dessert = state
    snake_set = set(current_snake)
    candidates = []
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if not active_mask[i][j]:
                continue
            if (i, j) in snake_set:
                continue
            if any((ni, nj) in snake_set for ni, nj in neighbors(i, j)):
                candidates.append((i, j))
    if not candidates:
        return state
    i, j = random.choice(candidates)
    new_state = (current_snake, copy.deepcopy(current_dessert))
    new_state[1][i][j] = not new_state[1][i][j]
    return new_state

# Simulated Annealing
def simulated_annealing(initial_state, time_limit=300):
    """
    Optimize the configuration (snake and dessert placements) using simulated annealing.
    Two move types:
      - With 70% probability, perform a snake move.
      - With 30% probability, perform a dessert move.
    The temperature cools slowly (total_iterations = 500,000) and the maximum runtime is 5 minutes.
    The search stops immediately if the temperature falls to 0.10.
    """
    current_state = initial_state
    current_score = total_score_state(current_state)
    best_state = current_state
    best_score = current_score

    start_time = time.time()
    iteration = 0
    T0 = 100.0
    T_end = 0.1
    total_iterations = 500000

    while time.time() - start_time < time_limit:
        iteration += 1
        frac = min(1.0, iteration / total_iterations)
        T = T0 * (1 - frac) + T_end * frac

        # Stop if temperature falls to 0.10
        if T <= 0.10:
            print("Temperature threshold reached. Stopping optimization.")
            break

        # Choose move type.
        if random.random() < 0.7:
            new_state = snake_move(current_state)
        else:
            new_state = dessert_move(current_state)

        new_score = total_score_state(new_state)
        delta = new_score - current_score

        if delta >= 0 or random.random() < math.exp(delta / T):
            current_state = new_state
            current_score = new_score
            if new_score > best_score:
                best_state = new_state
                best_score = new_score

        if iteration % 1000 == 0:
            print(f"Iteration {iteration:6d} | Current Score: {current_score:8.2f} | Best Score: {best_score:8.2f} | Temperature: {T:6.2f}")
    return best_state, best_score

# Display Final Layout (Softer Colors)
def display_layout(layout):
    """
    Display the final layout in a Tkinter window using soft colors:
      - Thickets ('T'): PaleGreen
      - Rivers ('R'): SkyBlue; if adjacent to a dessert (i.e. upgraded to oasis), shown as MediumTurquoise
      - Desserts ('D'): LightSalmon
      - Inactive ('I'): LightGray
    """
    window = tk.Tk()
    window.title("Final Layout")
    for i in range(HEIGHT):
        for j in range(WIDTH):
            cell = layout[i][j]
            if cell == 'T':
                bg = "PaleGreen"
            elif cell == 'R':
                # River cells adjacent to a dessert become oasis.
                if any(layout[ni][nj] == 'D' for ni, nj in neighbors(i, j)):
                    bg = "MediumTurquoise"
                else:
                    bg = "SkyBlue"
            elif cell == 'D':
                bg = "LightSalmon"
            else:  # 'I'
                bg = "LightGray"
            label = tk.Label(window, text="", width=2, height=1,
                             bg=bg, relief="flat", borderwidth=1)
            label.grid(row=i, column=j, padx=1, pady=1)
    window.mainloop()

# Main
def main():
    # 1. Let the user select active cells.
    run_selection()
    
    # 2. Choose a starting border cell (preferably far left or right, not in a corner).
    start = choose_start()
    if start is None:
        messagebox.showerror("Error", "No active border cell available!")
        return

    # 3. Build an initial snake starting at the chosen border cell.
    initial_snake = [start]  # snake is a list of (i,j) coordinates (all rivers)
    initial_snake = random_regrow(initial_snake, 0)
    
    # 4. Initialize dessert grid (all False).
    initial_dessert = init_dessert_mask()
    
    # 5. Initial state: (snake, dessert_mask)
    initial_state = (initial_snake, initial_dessert)
    init_score = total_score_state(initial_state)
    print("Initial snake length:", len(initial_snake), "Score:", init_score)

    # 6. Run simulated annealing for up to 5 minutes.
    best_state, best_score = simulated_annealing(initial_state, time_limit=300)
    best_layout = state_to_layout(best_state)
    print("Best snake length:", len(best_state[0]), "Best Score:", best_score)

    # 7. log the stats from the best layout on the console.
    # Base values
    attackSpeed = 0
    enemyAttackSpeed = 0
    everythingHealth = 100
    # Calculate the values of the layout based on the rules.
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if best_layout[i][j] == 'T':
                # Thickets increase in value based on the number of adjacent 'R' cells. 2 * 2^(# adjacent 'R' cells)
                attackSpeed += 2 * (2 ** sum(1 for ni, nj in neighbors(i, j) if best_layout[ni][nj] == 'R'))
            elif best_layout[i][j] == 'D':
                # Desserts increase in value based on the number of adjacent 'R' cells. -1 * 2^(# adjacent 'R' cells)
                everythingHealth += -1 * (2 ** sum(1 for ni, nj in neighbors(i, j) if best_layout[ni][nj] == 'R'))
            # Oasis cells
            elif best_layout[i][j] == 'R' and any(best_layout[ni][nj] == 'D' for ni, nj in neighbors(i, j)):
                # Oasis cells have flat value. -.5 attack speed, -1 enemy attack speed.
                attackSpeed -= .5
                enemyAttackSpeed -= 1
    # Cap the values to the minimums/maximums, just in case.
    if enemyAttackSpeed < -50:
        enemyAttackSpeed = -50
    if everythingHealth < 1:
        everythingHealth = 1

    print(f"Attack Speed: {attackSpeed}, Enemy Attack Speed: {enemyAttackSpeed}, Everything's Health: {everythingHealth}%")

    # 7. Display the final layout.
    display_layout(best_layout)

if __name__ == '__main__':
    main()
