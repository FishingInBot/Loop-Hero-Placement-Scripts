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

# UI for Selecting Active Cells and Oasis Value
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
                
        # Add a label and entry for maximum oasis
        self.max_oasis_label = tk.Label(self, text="Max Oasis:", justify="right")
        self.max_oasis_label.grid(row=HEIGHT, column=0, columnspan=3, sticky="ne", padx=5, pady=5)
        
        self.max_oasis_entry = tk.Entry(self, width=2)
        self.max_oasis_entry.grid(row=HEIGHT, column=3, columnspan=1, sticky="nw", padx=5, pady=5)
        self.max_oasis_entry.insert(0, "50")  # default value
        
        self.start_button = tk.Button(self, text="Start Optimization", command=self.on_start)
        self.start_button.grid(row=HEIGHT+1, column=0, columnspan=WIDTH, sticky="we", padx=5, pady=5)
        self.selected = False

    def toggle_cell(self, i, j):
        global active_mask
        active_mask[i][j] = not active_mask[i][j]
        btn = self.buttons[(i, j)]
        btn.config(bg="white" if active_mask[i][j] else "gray")

    def on_start(self):
        global MAX_OASIS
        try:
            MAX_OASIS = int(self.max_oasis_entry.get())
            if MAX_OASIS < 0:
                raise ValueError()
            if MAX_OASIS > 50:
                MAX_OASIS = 50
        except ValueError:
            messagebox.showerror("Error", "Invalid maximum oasis value!")
            return
        
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
# We now use a tuple: (snake, dessert_mask, suburb_mask)
def init_dessert_mask():
    return [[False for _ in range(WIDTH)] for _ in range(HEIGHT)]

def init_suburb_mask():
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
    # Otherwise, try top and bottom borders.
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
    Converts state (snake, dessert_mask, suburb_mask) to a layout.
    Snake cells:
      - Marked 'O' (oasis) if any adjacent active, non-snake cell has its dessert flag on,
      - otherwise 'R' (river).
    Non-snake active cells:
      - If flagged in suburb_mask: 'S'
      - Else if dessert flag is on and adjacent to snake: 'D'
      - Otherwise: 'T' (thicket)
    Finally, any thicket ('T') adjacent to a dessert ('D') becomes a Maquis tile ('M').
    Inactive cells are marked 'I'.
    """
    snake, dessert_mask, suburb_mask = state
    snake_set = set(snake)
    layout = []
    for i in range(HEIGHT):
        row = []
        for j in range(WIDTH):
            if not active_mask[i][j]:
                row.append('I')
            elif (i, j) in snake_set:
                oasis = False
                for ni, nj in neighbors(i, j):
                    if active_mask[ni][nj] and (ni, nj) not in snake_set and dessert_mask[ni][nj]:
                        oasis = True
                        break
                row.append('O' if oasis else 'R')
            else:
                if suburb_mask[i][j]:
                    row.append('S')
                elif dessert_mask[i][j] and any((ni, nj) in snake_set for ni, nj in neighbors(i, j)):
                    row.append('D')
                else:
                    row.append('T')
        layout.append(row)
    # Convert thicket tiles to Maquis if adjacent to a dessert tile.
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if layout[i][j] == 'T':
                if any(layout[ni][nj] == 'D' for ni, nj in neighbors(i, j)):
                    layout[i][j] = 'M'
    return layout

# Scoring Functions
def total_score_layout(layout):
    """
    Total score is the sum of:
      - Thicket bonus: For each thicket ('T'), bonus = 2 * 2^(# adjacent River cells).
      - Oasis bonus: 30 points per oasis, capped at MAX_OASIS cells.
      - Suburb bonus: Each suburb ('S') gives a base bonus of 1 (or 2 if surrounded on all 4 sides)
        multiplied by 2^(# adjacent River cells), summed and then scaled (10×) but capped to 25 total bonus.
      - Maquis tiles ('M') lose the thicket bonus. Here we subtract half the thicket bonus they would have given.
    """
    score = 0.0
    # Thicket bonus:
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if layout[i][j] == 'T':
                count = sum(1 for ni, nj in neighbors(i, j) if layout[ni][nj] in ['R'])
                score += 2 * (2 ** count)
    # Oasis bonus:
    oasis_count = sum(1 for i in range(HEIGHT) for j in range(WIDTH) if layout[i][j]=='O')
    score += 30 * min(oasis_count, MAX_OASIS)
    # Suburb bonus:
    suburb_bonus_total = 0
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if layout[i][j] == 'S':
                suburb_neighbors = sum(1 for ni, nj in neighbors(i, j) if layout[ni][nj] == 'S')
                base = 2 if suburb_neighbors == 4 else 1
                river_count = sum(1 for ni, nj in neighbors(i, j) if layout[ni][nj] in ['R'])
                bonus = base * (2 ** river_count)
                suburb_bonus_total += bonus
    suburb_score = 10 * min(suburb_bonus_total, 25)
    score += suburb_score
    # Maquis penalty:
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if layout[i][j] == 'M':
                count = sum(1 for ni, nj in neighbors(i, j) if layout[ni][nj] in ['R'])
                score -= 2 * (2 ** count) * 0.5
    return score

def total_score_state(state):
    layout = state_to_layout(state)
    return total_score_layout(layout)

# Snake Moves (Connectivity Moves)
def random_regrow(snake, trunc_index):
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
    current_snake, current_dessert, current_suburb = state
    if len(current_snake) <= 1:
        return state
    trunc_index = random.randint(0, len(current_snake) - 1)
    new_snake = random_regrow(current_snake, trunc_index)
    new_dessert = copy.deepcopy(current_dessert)
    for (i, j) in new_snake:
        new_dessert[i][j] = False
    return (new_snake, new_dessert, current_suburb)

def dessert_move(state):
    current_snake, current_dessert, current_suburb = state
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
    new_dessert = copy.deepcopy(current_dessert)
    new_dessert[i][j] = not new_dessert[i][j]
    return (current_snake, new_dessert, current_suburb)

def valid_suburb_cluster(suburb_mask):
    # Gather all suburb cells.
    cells = [(i, j) for i in range(HEIGHT) for j in range(WIDTH) if suburb_mask[i][j]]
    # If there's only one suburb tile, isolation isn't a concern.
    if len(cells) <= 1:
        return True
    # Otherwise, every suburb cell must have at least one adjacent suburb cell.
    for i, j in cells:
        if not any(suburb_mask[ni][nj] for ni, nj in neighbors(i, j)):
            return False
    return True

def suburb_move(state):
    current_snake, current_dessert, current_suburb = state
    suburb_exists = any(current_suburb[i][j] for i in range(HEIGHT) for j in range(WIDTH))
    candidates = []
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if not active_mask[i][j]:
                continue
            if (i, j) in current_snake:
                continue
            # Only consider cells not already marked as suburb.
            if current_suburb[i][j]:
                continue
            # If a suburb already exists, new additions must be adjacent.
            if suburb_exists:
                if any(current_suburb[ni][nj] for ni, nj in neighbors(i, j)):
                    # Simulate the addition.
                    new_suburb = copy.deepcopy(current_suburb)
                    new_suburb[i][j] = True
                    if valid_suburb_cluster(new_suburb):
                        candidates.append((i, j))
            else:
                # No suburb exists yet; any cell is allowed.
                new_suburb = copy.deepcopy(current_suburb)
                new_suburb[i][j] = True
                if valid_suburb_cluster(new_suburb):
                    candidates.append((i, j))
    if not candidates:
        return state
    i, j = random.choice(candidates)
    new_suburb = copy.deepcopy(current_suburb)
    new_suburb[i][j] = True
    return (current_snake, current_dessert, new_suburb)


# Simulated Annealing
def simulated_annealing(initial_state, time_limit=300):
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

        if T <= 0.10:
            print("Temperature threshold reached. Stopping optimization.")
            break

        r = random.random()
        if r < 0.6:
            new_state = snake_move(current_state)
        elif r < 0.85:
            new_state = dessert_move(current_state)
        else:
            new_state = suburb_move(current_state)

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
    window = tk.Tk()
    window.title("Final Layout")
    for i in range(HEIGHT):
        for j in range(WIDTH):
            cell = layout[i][j]
            if cell == 'T':
                bg = "PaleGreen"
            elif cell == 'M':
                bg = "LightGreen"
            elif cell == 'R':
                bg = "SkyBlue"
            elif cell == 'O':
                bg = "MediumTurquoise"
            elif cell == 'D':
                bg = "LightSalmon"
            elif cell == 'S':
                bg = "Khaki"
            else:  # 'I'
                bg = "LightGray"
            label = tk.Label(window, text=cell, width=2, height=1,
                             bg=bg, relief="flat", borderwidth=1)
            label.grid(row=i, column=j, padx=1, pady=1)
    window.mainloop()

# Main
def main():
    run_selection()
    start = choose_start()
    if start is None:
        messagebox.showerror("Error", "No active border cell available!")
        return

    initial_snake = [start]
    initial_snake = random_regrow(initial_snake, 0)
    initial_dessert = init_dessert_mask()
    initial_suburb = init_suburb_mask()
    initial_state = (initial_snake, initial_dessert, initial_suburb)
    init_score = total_score_state(initial_state)
    print("Initial snake length:", len(initial_snake), "Score:", init_score)

    best_state, best_score = simulated_annealing(initial_state, time_limit=300)
    best_layout = state_to_layout(best_state)
    print("Best snake length:", len(best_state[0]), "Best Score:", best_score)

    # Final stats calculation
    attackSpeed = 0
    enemyAttackSpeed = 0
    everythingHealth = 100
    maquis_attack_bonus = 0
    maquis_enemy_bonus = 0
    xp_bonus_total = 0
    for i in range(HEIGHT):
        for j in range(WIDTH):
            if best_layout[i][j] == 'T':
                count = sum(1 for ni, nj in neighbors(i, j) if best_layout[ni][nj] in ['R'])
                attackSpeed += 2 * (2 ** count)
            elif best_layout[i][j] == 'M':
                count = sum(1 for ni, nj in neighbors(i, j) if best_layout[ni][nj] in ['R'])
                bonus = 2 * (2 ** count)
                maquis_attack_bonus += bonus
                maquis_enemy_bonus += bonus
            elif best_layout[i][j] == 'D':
                everythingHealth += -1
            elif best_layout[i][j] == 'O':
                attackSpeed -= 0.5
                enemyAttackSpeed -= 1
            elif best_layout[i][j] == 'S':
                suburb_neighbors = sum(1 for ni, nj in neighbors(i, j) if best_layout[ni][nj] == 'S')
                base = 2 if suburb_neighbors == 4 else 1
                river_count = sum(1 for ni, nj in neighbors(i, j) if best_layout[ni][nj] in ['R'])
                xp_bonus_total += base * (2 ** river_count)
    # Cap maquis stacking (25 times max, so bonus capped at 50)
    maquis_attack_bonus = min(maquis_attack_bonus, 50)
    maquis_enemy_bonus = min(maquis_enemy_bonus, 50)
    attackSpeed += maquis_attack_bonus
    enemyAttackSpeed -= maquis_enemy_bonus
    xp_bonus_total = min(xp_bonus_total, 25)

    print(f"Attack Speed: {attackSpeed}, Enemy Attack Speed: {enemyAttackSpeed}, Everything's Health: {everythingHealth}%")
    print(f"XP Bonus per kill: {xp_bonus_total}")
    display_layout(best_layout)

if __name__ == '__main__':
    main()
