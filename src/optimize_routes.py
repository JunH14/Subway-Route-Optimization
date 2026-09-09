"""Run the final '개체 개선 알고리즘' cell from the original project.

The research functions are preserved. This wrapper adds configurable paths,
input checks, trial limits, an optional seed, and optional result export.
See docs/methodology.md for the original algorithm's limitations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

INPUTS = {
    "엣지데이터 신규.xlsx": ["from", "to", "from_lon", "from_lat", "to_lon", "to_lat", "distance"],
    "역 경도 위도.xlsx": ["역명", "위도", "경도"],
    "쌍가중치_정규화_OD.xlsx": ["승차_역", "하차_역", "쌍_가중치_정규화"],
    "총점수_정규화_역주변시설.xlsx": ["역명", "총점수_정규화"],
}
TERMINALS = {
    "천왕", "지축", "역곡", "회룡", "하남검단산", "방화", "독바위", "신내",
    "불암산", "남태령", "개화", "중앙보훈병원", "수락산", "마천", "암사", "모란",
}


def load_inputs(data_dir):
    """Read the four original Excel inputs, without changing their values."""
    data_dir = Path(data_dir).expanduser()
    missing = [name for name in INPUTS if not (data_dir / name).is_file()]
    if missing:
        raise ValueError("Missing input files in " + str(data_dir) + ": " + ", ".join(missing))
    frames = []
    for name, columns in INPUTS.items():
        frame = pd.read_excel(data_dir / name, sheet_name="Sheet1" if name == "역 경도 위도.xlsx" else 0)
        absent = sorted(set(columns) - set(frame.columns))
        if absent:
            raise ValueError(f"{name}: missing columns {absent}")
        if frame.empty:
            raise ValueError(f"{name}: the input table is empty")
        frames.append(frame)
    edges, nodes, od, scores = frames
    od = od.dropna(subset=["승차_역", "하차_역"])
    if od.empty:
        raise ValueError("The OD table has no non-empty station pairs")
    checks = [
        (edges, ["from_lon", "from_lat", "to_lon", "to_lat", "distance"], "edges"),
        (nodes, ["위도", "경도"], "stations"),
        (od, ["쌍_가중치_정규화"], "OD scores"),
        (scores, ["총점수_정규화"], "facility scores"),
    ]
    for frame, columns, label in checks:
        numeric = frame[columns].apply(pd.to_numeric, errors="coerce")
        if not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise ValueError(f"{label}: required numeric values must be finite and non-empty")
    for frame, columns in [(edges, ["from", "to"]), (nodes, ["역명"]), (od, ["승차_역", "하차_역"]), (scores, ["역명"])]:
        for column in columns:
            if not frame[column].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
                raise ValueError(f"{column}: station names must be non-empty strings")
    if (edges["distance"] <= 0).any():
        raise ValueError("Edge distances must be positive")
    graph_nodes = set(edges["from"]) | set(edges["to"])
    missing_terminals = sorted(TERMINALS - graph_nodes)
    if missing_terminals:
        raise ValueError(f"The edge table is missing configured terminal stations: {missing_terminals}")
    print(f"Inputs: {len(nodes)} station rows, {len(edges)} edge rows, {len(od)} OD rows, {len(scores)} facility rows", flush=True)
    return edges, nodes, od, scores


def run_optimization(data_dir, *, trials=100000, iterations=10000, seed=None, top_k=10, show=True, output_dir=None):
    """Execute the archived final experiment with an optional runtime configuration."""
    if trials < 1 or iterations < 0 or top_k < 1:
        raise ValueError("trials and top_k must be positive; iterations must be non-negative")
    if not show:
        import matplotlib
        matplotlib.use("Agg")
    import pandas as pd
    import numpy as np
    import networkx as nx
    import matplotlib.pyplot as plt
    import random
    from heapq import heappush, heappop


    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    df_edges, df_nodes, df_od, df_node_score = load_inputs(data_dir)
    destination = Path(output_dir) if output_dir is not None else None
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=True)

    def finish_plot(fig, filename):
        if destination is not None:
            fig.savefig(destination / filename, dpi=160, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)

    od_weight_dict = df_od.set_index(['승차_역', '하차_역'])['쌍_가중치_정규화'].to_dict()
    node_score_dict = df_node_score.set_index('역명')['총점수_정규화'].to_dict()

    G_base = nx.Graph()
    for _, row in df_edges.iterrows():
        u, v = row['from'], row['to']
        pos_u = (row['from_lon'], row['from_lat'])
        pos_v = (row['to_lon'], row['to_lat'])
        dist = row['distance']
        G_base.add_node(u, pos=pos_u)
        G_base.add_node(v, pos=pos_v)
        G_base.add_edge(u, v, weight=dist)

    def heuristic(a, b):
        return np.linalg.norm(np.array(a) - np.array(b))

    def random_a_star(graph, start, goal, used_edges):
        open_set = []
        heappush(open_set, (0, start))
        came_from = {}
        g_score = {node: float('inf') for node in graph.nodes}
        g_score[start] = 0
        f_score = {node: float('inf') for node in graph.nodes}
        f_score[start] = heuristic(graph.nodes[start]['pos'], graph.nodes[goal]['pos'])

        while open_set:
            _, current = heappop(open_set)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]

            neighbors = list(graph.neighbors(current))
            random.shuffle(neighbors)
            for neighbor in neighbors:
                edge = tuple(sorted((current, neighbor)))
                if edge in used_edges:
                    continue
                tentative_g = g_score[current] + graph[current][neighbor]['weight']
                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + heuristic(graph.nodes[neighbor]['pos'], graph.nodes[goal]['pos'])
                    heappush(open_set, (f_score[neighbor], neighbor))
        return None

    line2_station_names = ['시청', '을지로입구', '을지로3가', '을지로4가', '동대문역사문화공원',
        '신당', '상왕십리', '왕십리', '한양대', '뚝섬', '성수', '건대입구', '구의', '강변', '잠실나루',
        '잠실', '잠실새내', '종합운동장', '삼성', '선릉', '역삼', '강남', '교대', '서초', '방배',
        '사당', '낙성대', '서울대입구', '봉천', '신림', '신대방', '구로디지털단지', '대림',
        '신도림', '문래', '영등포구청', '당산', '합정', '홍대입구', '신촌', '이대', '아현', '충정로', '시청']
    line2_nodes = [s for s in line2_station_names if s in G_base.nodes]
    line2_path = []
    line2_edges = set()
    for u, v in zip(line2_nodes[:-1], line2_nodes[1:]):
        if not G_base.has_edge(u, v):
            dist = np.linalg.norm(np.array(G_base.nodes[u]['pos']) - np.array(G_base.nodes[v]['pos']))
            G_base.add_edge(u, v, weight=dist)
        line2_edges.add(tuple(sorted((u, v))))
        if not line2_path or line2_path[-1] != u:
            line2_path.extend([u, v])
        else:
            line2_path.append(v)

    def fitness_path_length_range(individual, min_length=20, max_length=50):
        penalty = 0
        for line_num, path in individual:
            if line_num == 100: continue
            if len(path) < min_length:
                penalty += (min_length - len(path))**2
            elif len(path) > max_length:
                penalty += (len(path) - max_length)**2
        return -penalty

    # 각도 변화량 패널티
    def angle_between_nodes(pos_u, pos_v, pos_w):
        vec1 = np.array(pos_u) - np.array(pos_v)
        vec2 = np.array(pos_w) - np.array(pos_v)
        cosine = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        cosine = np.clip(cosine, -1.0, 1.0)
        return np.degrees(np.arccos(cosine))

    def smooth_angle_penalty(line_paths, graph):
        penalty = 0
        for _, path in line_paths:
            if len(path) < 4:
                continue

            # 단일 각도 기준 (급격한 꺾임 탐지)
            for i in range(1, len(path) - 1):
                u, v, w = path[i - 1], path[i], path[i + 1]
                angle = angle_between_nodes(graph.nodes[u]['pos'], graph.nodes[v]['pos'], graph.nodes[w]['pos'])
                if angle < 90:
                    penalty += (90 - angle)

            # 연속 각도의 변화량 기준
            for i in range(1, len(path) - 2):
                u1, v1, w1 = path[i - 1], path[i], path[i + 1]
                u2, v2, w2 = path[i], path[i + 1], path[i + 2]

                angle1 = angle_between_nodes(graph.nodes[u1]['pos'], graph.nodes[v1]['pos'], graph.nodes[w1]['pos'])
                angle2 = angle_between_nodes(graph.nodes[u2]['pos'], graph.nodes[v2]['pos'], graph.nodes[w2]['pos'])

                penalty += (abs(angle1 - angle2))

        return -penalty

    # 35도 이하는 생성 금지
    def is_individual_angle_valid(individual, graph, min_angle=35):
        for _, path in individual:
            if len(path) < 3:
                continue
            for i in range(1, len(path) - 1):
                u, v, w = path[i - 1], path[i], path[i + 1]
                angle = angle_between_nodes(graph.nodes[u]['pos'], graph.nodes[v]['pos'], graph.nodes[w]['pos'])
                if angle < min_angle:
                    return False
        return True


    # 종합 적합도 함수
    def calculate_combined_fitness(line_paths, od_dict, node_dict,
                                    alpha=1.0, beta=2.5, gamma=0.1, delta=0.013):
        od_score = 0
        for _, path in line_paths:
            for i in range(len(path)):
                for j in range(i + 1, len(path)):
                    pair = (path[i], path[j])
                    rev_pair = (path[j], path[i])
                    if pair in od_dict:
                        od_score += od_dict[pair]
                    elif rev_pair in od_dict:
                        od_score += od_dict[rev_pair]

        node_score = sum(node_dict.get(n, 0) for _, path in line_paths for n in path)
        length_penalty = fitness_path_length_range(line_paths)
        angle_penalty_val = smooth_angle_penalty(line_paths, G_base)

        return alpha * od_score + beta * node_score + gamma * length_penalty + delta * angle_penalty_val

    ### 개선 할때 60미만 각도 우선 추출
    def improve_individual_by_angle_with_batch_insertion(individual, graph, min_angle=60, batch_size=4):
        improved = [ (lnum, path[:]) for lnum, path in individual ]
        candidates = []

        # 각도 min_angle 미만인 지점 수집
        for line_idx, (lnum, path) in enumerate(improved):
            if lnum == 100 or len(path) < 3:
                continue
            for i in range(1, len(path) - 1):
                u, v, w = path[i - 1], path[i], path[i + 1]
                angle = angle_between_nodes(graph.nodes[u]['pos'], graph.nodes[v]['pos'], graph.nodes[w]['pos'])
                if angle < min_angle:
                    candidates.append((line_idx, i, v))

        if not candidates:
            return improved

        selected = random.sample(candidates, min(batch_size, len(candidates)))
        removed_nodes = []

        for line_idx, del_idx, bad_node in selected:
            lnum, path = improved[line_idx]
            if del_idx < len(path):
                new_path = path[:del_idx] + path[del_idx+1:]
                improved[line_idx] = (lnum, new_path)
                removed_nodes.append(bad_node)

        for bad_node in removed_nodes:
            best_dist = float('inf')
            best_insert = None

            for i, (lnum2, path2) in enumerate(improved):
                if len(path2) < 2:
                    continue
                for j in range(len(path2) - 1):
                    a, b = path2[j], path2[j + 1]
                    pos_a = graph.nodes[a]['pos']
                    pos_b = graph.nodes[b]['pos']
                    pos_v = graph.nodes[bad_node]['pos']
                    dist = np.linalg.norm(np.array(pos_v) - (np.array(pos_a) + np.array(pos_b)) / 2)
                    if dist < best_dist:
                        best_dist = dist
                        best_insert = (i, j + 1)

            if best_insert:
                i, insert_pos = best_insert
                lnum2, path2 = improved[i]
                if bad_node not in path2:
                    a = path2[insert_pos - 1]
                    b = path2[insert_pos]
                    if not graph.has_edge(a, bad_node):
                        dist1 = np.linalg.norm(np.array(graph.nodes[a]['pos']) - np.array(graph.nodes[bad_node]['pos']))
                        graph.add_edge(a, bad_node, weight=dist1)
                    if not graph.has_edge(bad_node, b):
                        dist2 = np.linalg.norm(np.array(graph.nodes[bad_node]['pos']) - np.array(graph.nodes[b]['pos']))
                        graph.add_edge(bad_node, b, weight=dist2)

                    new_path2 = path2[:insert_pos] + [bad_node] + path2[insert_pos:]
                    improved[i] = (lnum2, new_path2)

        return improved


    def improve_by_batch_safe_granular(individual, graph, od_dict, node_dict, iterations=10, batch_size=4, min_angle=60):
        current = [ (lnum, path[:]) for lnum, path in individual ]
        current_score = calculate_combined_fitness(current, od_dict, node_dict)

        for _ in range(iterations):
            # 꺾인 점 후보 수집
            candidates = []
            for line_idx, (lnum, path) in enumerate(current):
                if lnum == 100 or len(path) < 3:
                    continue
                for i in range(1, len(path) - 1):
                    u, v, w = path[i - 1], path[i], path[i + 1]
                    angle = angle_between_nodes(graph.nodes[u]['pos'], graph.nodes[v]['pos'], graph.nodes[w]['pos'])
                    if angle < min_angle:
                        candidates.append((line_idx, i, v))

            if not candidates:
                break  # 개선할 점이 없음

            selected = random.sample(candidates, min(batch_size, len(candidates)))

            for line_idx, del_idx, bad_node in selected:
                # 현재 상태를 복사
                trial = [ (lnum, path[:]) for lnum, path in current ]
                lnum, path = trial[line_idx]

                # 노드 제거
                if del_idx >= len(path): continue
                path = path[:del_idx] + path[del_idx+1:]
                trial[line_idx] = (lnum, path)

                # 삽입 위치 탐색
                best_dist = float('inf')
                best_insert = None
                for i, (lnum2, path2) in enumerate(trial):
                    if len(path2) < 2 or bad_node in path2: continue
                    for j in range(len(path2) - 1):
                        a, b = path2[j], path2[j + 1]
                        pos_a = graph.nodes[a]['pos']
                        pos_b = graph.nodes[b]['pos']
                        pos_v = graph.nodes[bad_node]['pos']
                        dist = np.linalg.norm(np.array(pos_v) - (np.array(pos_a) + np.array(pos_b)) / 2)
                        if dist < best_dist:
                            best_dist = dist
                            best_insert = (i, j + 1)

                # 삽입 시도
                if best_insert:
                    i, insert_pos = best_insert
                    lnum2, path2 = trial[i]
                    a = path2[insert_pos - 1]
                    b = path2[insert_pos]
                    if not graph.has_edge(a, bad_node):
                        dist1 = np.linalg.norm(np.array(graph.nodes[a]['pos']) - np.array(graph.nodes[bad_node]['pos']))
                        graph.add_edge(a, bad_node, weight=dist1)
                    if not graph.has_edge(bad_node, b):
                        dist2 = np.linalg.norm(np.array(graph.nodes[bad_node]['pos']) - np.array(graph.nodes[b]['pos']))
                        graph.add_edge(bad_node, b, weight=dist2)
                    new_path2 = path2[:insert_pos] + [bad_node] + path2[insert_pos:]
                    trial[i] = (lnum2, new_path2)

                # 개선 여부 판단
                trial_score = calculate_combined_fitness(trial, od_dict, node_dict)
                if trial_score >= current_score:
                    current = trial
                    current_score = trial_score


        return current



    custom_terminal_pairs = [
        ('천왕', '지축'), ('역곡', '회룡'), ('하남검단산', '방화'), ('독바위', '신내'),
        ('불암산', '남태령'), ('개화', '중앙보훈병원'), ('수락산', '마천'), ('암사', '모란')
    ]

    population = []
    fitness_scores = []
    for trial_index in range(trials):
        if trial_index % max(1, trials // 10) == 0:
            print(f"Candidates: {trial_index}/{trials}; accepted: {len(population)}", flush=True)
        G = G_base.copy()
        for u, v in G.edges():
            dist = np.linalg.norm(np.array(G.nodes[u]['pos']) - np.array(G.nodes[v]['pos']))
            G[u][v]['weight'] = dist * random.uniform(0.1, 1.9)

        used_edges = set(line2_edges)
        line_paths = [(100, line2_path)]
        valid = True

        for i, (start, goal) in enumerate(custom_terminal_pairs):
            path = random_a_star(G, start, goal, used_edges)
            if path is None:
                valid = False
                break
            for u, v in zip(path[:-1], path[1:]):
                used_edges.add(tuple(sorted((u, v))))
            line_paths.append((i, path))

        if not valid or len(line_paths) != 9:
            continue


        all_nodes = set(G_base.nodes)
        covered = set(n for _, p in line_paths for n in p)
        missing = sorted(all_nodes - covered) if seed is not None else list(all_nodes - covered)

        # 미포함 노드 포함시키는 로직
        for mn in missing:
            best_increase = float('inf')
            for i, (lnum, path) in enumerate(line_paths):
                if lnum == 100: continue
                for j in range(len(path)-1):
                    u, v = path[j], path[j+1]
                    cost_now = np.linalg.norm(np.array(G_base.nodes[u]['pos']) - np.array(G_base.nodes[v]['pos']))
                    cost_new = np.linalg.norm(np.array(G_base.nodes[u]['pos']) - np.array(G_base.nodes[mn]['pos'])) + \
                               np.linalg.norm(np.array(G_base.nodes[mn]['pos']) - np.array(G_base.nodes[v]['pos']))
                    if cost_new - cost_now < best_increase:
                        best = (i, j+1)
                        best_increase = cost_new - cost_now
            if best_increase < float('inf'):
                i, pos = best
                lnum, path = line_paths[i]
                line_paths[i] = (lnum, path[:pos] + [mn] + path[pos:])

        # 초기 후보: 기본값 35도 미만 각도가 있으면 폐기
        if not is_individual_angle_valid(line_paths, G_base):
            continue

        population.append(line_paths)
        fitness_scores.append(calculate_combined_fitness(line_paths, od_weight_dict, node_score_dict))


    print(f"Candidates: {trials}/{trials}; accepted: {len(population)}", flush=True)
    if not population:
        raise RuntimeError(
            "No valid nine-line candidate was found. Increase --trials or change --seed. "
            "Small trial counts can fail even with valid input files."
        )
    top_10_indices = np.argsort(fitness_scores)[-top_k:][::-1]

    line_colors = {
        1: '#0052A4', 2: '#00A84D', 3: '#EF7C1C', 4: '#00A0DE', 5: '#996CAC',
        6: '#CD7C2F', 7: '#747F00', 8: '#E6186C', 9: '#B7C452'
    }


    for rank, idx in enumerate(top_10_indices, 1):
        solution = population[idx]
        score = fitness_scores[idx]

        fig, ax = plt.subplots(figsize=(6, 6))
        for line_num, path in solution:
            if line_num == 100:
                color = line_colors[2]
                label = 'Line 2'
            else:
                corrected_line = line_num + 1 if line_num < 1 else line_num + 2
                color = line_colors.get(corrected_line, 'gray')
                label = f'Line {corrected_line}'

            for u, v in zip(path[:-1], path[1:]):
                x1, y1 = G_base.nodes[u]['pos']
                x2, y2 = G_base.nodes[v]['pos']
                if u == path[0]:
                    ax.plot([x1, x2], [y1, y2], color=color, linewidth=2.5, label=label)
                else:
                    ax.plot([x1, x2], [y1, y2], color=color, linewidth=2.5)

        for _, data in G_base.nodes(data=True):
            ax.plot(data['pos'][0], data['pos'][1], 'k.', markersize=3)

        handles, labels = ax.get_legend_handles_labels()
        sorted_labels_handles = sorted(zip(labels, handles), key=lambda x: int(x[0].split()[-1]))
        labels, handles = zip(*sorted_labels_handles)
        ax.legend(handles, labels, loc='best')

        plt.title(f"Rank {rank} | Score: {score:.2f}", fontsize=10)
        plt.axis('off')
        finish_plot(fig, f"rank_{rank:02d}.png")


    # top 1 개체 선택
    original = population[top_10_indices[0]]

    # 개선: 점수 기반 유지
    improved = improve_by_batch_safe_granular(
        original, G_base, od_weight_dict, node_score_dict,
        iterations=iterations,
        batch_size=4,
        min_angle=60
    )


    # 점수 비교
    before_score = calculate_combined_fitness(original, od_weight_dict, node_score_dict)
    after_score = calculate_combined_fitness(improved, od_weight_dict, node_score_dict)

    print(f"before score: {before_score:.2f} → after score: {after_score:.2f}")

    # 개선된 개체 시각화
    fig, ax = plt.subplots(figsize=(6, 6))
    for line_num, path in improved:
        if line_num == 100:
            color = line_colors[2]
            label = 'Line 2'
        else:
            corrected_line = line_num + 1 if line_num < 1 else line_num + 2
            color = line_colors.get(corrected_line, 'gray')
            label = f'Line {corrected_line}'

        for u, v in zip(path[:-1], path[1:]):
            x1, y1 = G_base.nodes[u]['pos']
            x2, y2 = G_base.nodes[v]['pos']
            if u == path[0]:
                ax.plot([x1, x2], [y1, y2], color=color, linewidth=2.5, label=label)
            else:
                ax.plot([x1, x2], [y1, y2], color=color, linewidth=2.5)

    for _, data in G_base.nodes(data=True):
        ax.plot(data['pos'][0], data['pos'][1], 'k.', markersize=3)

    handles, labels = ax.get_legend_handles_labels()
    sorted_labels_handles = sorted(zip(labels, handles), key=lambda x: int(x[0].split()[-1]))
    labels, handles = zip(*sorted_labels_handles)
    ax.legend(handles, labels, loc='best')

    plt.title(f"After Score: {after_score:.2f}", fontsize=10)
    plt.axis('off')
    finish_plot(fig, "improved.png")

    result = {
        "trials": trials,
        "iterations": iterations,
        "seed": seed,
        "accepted_candidates": len(population),
        "before_score": float(before_score),
        "after_score": float(after_score),
        "before_routes": [{"line_id": int(lnum), "stations": path} for lnum, path in original],
        "after_routes": [{"line_id": int(lnum), "stations": path} for lnum, path in improved],
        "notes": "Notebook research objective. Line id 100 denotes Line 2. See docs/methodology.md.",
    }
    if destination is not None:
        (destination / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data", help="Directory containing the four original Excel files")
    parser.add_argument("--trials", type=int, default=100000, help="Candidate generation attempts (original: 100000)")
    parser.add_argument("--iterations", type=int, default=10000, help="Local improvement iterations (original: 10000)")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed; also sorts uncovered stations")
    parser.add_argument("--top-k", type=int, default=10, help="Number of initial candidates to plot")
    parser.add_argument("--no-show", action="store_true", help="Use a non-interactive plotting backend")
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional destination for PNG figures and result.json")
    parser.add_argument("--check-data", action="store_true", help="Validate inputs without generating candidates")
    args = parser.parse_args()
    if args.trials < 1 or args.iterations < 0 or args.top_k < 1:
        parser.error("--trials and --top-k must be positive; --iterations must be non-negative")
    if args.seed is not None and not 0 <= args.seed < 2**32:
        parser.error("--seed must be between 0 and 2**32 - 1")
    try:
        if args.check_data:
            load_inputs(args.data_dir)
            print("Input checks passed.")
        else:
            run_optimization(args.data_dir, trials=args.trials, iterations=args.iterations,
                             seed=args.seed, top_k=args.top_k, show=not args.no_show,
                             output_dir=args.output_dir)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
