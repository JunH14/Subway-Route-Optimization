# Subway Route Optimization

서울 지하철 역 좌표와 통행 수요(OD), 역 주변 시설 정보를 활용한 **그래프 기반 대안 노선망 설계 프로젝트**입니다. 초기 그래프와 후보 노선을 생성한 뒤, 수요·시설 접근성과 노선 형태를 함께 평가하고 국소 개선을 적용합니다.

[원본 Colab](https://colab.research.google.com/drive/1vkkMl_U6d2DW5AsHdCG_M6r5SFv_xa1h) · [전체 실험 노트북](notebooks/subway_route_optimization.ipynb) · [최종 실행 코드](src/optimize_routes.py) · [데이터 안내](data/README.md)

## 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 문제 | 기존 노선망의 연결 구조와 급격한 꺾임 등을 고려한 대안 노선 설계 |
| 입력 | 역 좌표, 후보 엣지, 정규화된 OD 가중치, 역 주변 시설 점수 |
| 노선 구성 | 2호선 순환 경로와 8개 종착역 쌍을 이용한 9개 노선 후보 |
| 주요 기법 | KDTree, A* 계열 탐색, MST 비교, 기하 규칙, Simulated Annealing 실험, 국소 개선 |
| 구현 | Python, pandas, NumPy, NetworkX, SciPy, Matplotlib |

## 분석 과정

1. **좌표와 초기 그래프**: 역 위치를 시각화하고, 가까운 이웃과 A* 경로로 초기 연결 구조를 구성합니다. MST 기반 구성도 비교합니다.
2. **노선 후보 생성**: 부분 경로, 역 그룹화, 2호선 순환 경로, 둔각 삼각형의 긴 변 제거를 실험합니다.
3. **수요와 시설 반영**: OD 가중치와 역 주변 시설 점수를 노선 평가에 결합합니다.
4. **최종 실험**: 엣지 가중치에 난수를 적용해 9개 노선 후보를 만들고, 미포함 역 삽입과 초기 각도 조건을 적용합니다.
5. **국소 개선**: 꺾임이 있는 역을 재배치하는 후보를 평가하고, 종합 적합도가 떨어지지 않는 변경을 채택합니다.

최종 적합도는 `1.0 × OD 점수 + 2.5 × 시설 점수 + 0.1 × 길이 패널티 + 0.013 × 각도 패널티`입니다. 두 패널티는 0 이하이며, 여기서 길이는 실제 km가 아니라 **경로에 포함된 역 수**를 뜻합니다. 자세한 계산과 구현 범위는 [방법론](docs/methodology.md)에 정리했습니다.

## 실행 방법

### Colab

1. [GitHub 노트북을 Colab에서 열기](https://colab.research.google.com/github/JunH14/Subway-Route-Optimization/blob/main/notebooks/subway_route_optimization.ipynb)
2. [필수 엑셀 4개](data/README.md)를 Colab의 `/content/`에 업로드합니다.
3. 마지막 **`개체 개선 알고리즘`** 코드 셀을 실행합니다. 이 셀은 최종 실험에 필요한 import와 함수를 자체적으로 포함합니다.

전체 노트북은 실험 기록이므로 각 실험을 선택해 실행합니다. 위에서부터 모두 실행하려면 중간 실험용 파일도 필요합니다. 원본의 최종 설정은 후보 생성 100,000회, 국소 개선 10,000회로 실행 시간이 길 수 있습니다.

### 로컬 / VS Code

Python 3.10 이상을 사용합니다. 아래 명령은 macOS/Linux 기준입니다.

```bash
git clone https://github.com/JunH14/Subway-Route-Optimization.git
cd Subway-Route-Optimization
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

엑셀 4개를 `data/`에 넣고 먼저 입력을 확인합니다.

```bash
python src/optimize_routes.py --data-dir ./data --check-data
```

원본과 같은 반복 횟수로 실행하고, 선택적으로 결과를 저장합니다.

```bash
python src/optimize_routes.py --data-dir ./data --seed 42 --output-dir ./outputs
```

짧은 동작 확인은 다음과 같이 실행할 수 있습니다. 시도 횟수가 적으면 유효한 후보가 하나도 생성되지 않을 수 있으며, 이때 실행기는 이유를 출력하고 종료합니다.

```bash
python src/optimize_routes.py --data-dir ./data --trials 100 --iterations 10 --top-k 1 --seed 42 --no-show --output-dir ./outputs/smoke
```

`--output-dir`을 지정하면 후보 그림, 개선 후 그림과 경로·점수가 담긴 `result.json`을 저장합니다. 옵션을 생략하면 결과 파일을 저장하지 않습니다. VS Code에서는 저장소 폴더를 열고 `.venv`의 Python 인터프리터를 선택합니다.

## 파일 안내

| 경로 | 내용 |
| --- | --- |
| `notebooks/subway_route_optimization.ipynb` | 원본 33개 셀의 소스와 순서를 보존한 실험 기록. 실행 출력과 임시 메타데이터 정리 |
| `src/optimize_routes.py` | 원본 마지막 셀에 경로·반복 횟수·시드·입력 검사·결과 저장 옵션을 추가한 실행기 |
| `requirements.txt` | 최종 실행기 의존성 |
| `requirements-exploration.txt` | 지도, OSM 시설 조회 등 중간 실험용 추가 의존성 |
| `data/README.md` | 필요한 데이터 파일과 열 구조 |
| `docs/methodology.md` | 점수 계산, 실험 범위, 원본 구현의 한계 |
| `docs/provenance.json` | 원본 링크, 셀 수와 원본 파일 해시 |

입력 엑셀은 이 저장소에 포함되어 있지 않습니다. 노트북에 필요한 파일은 `data/README.md`를 참고하세요.

## 원본과 후속 과제

원본: **프로젝트 학기 유정이 최종 성과물**, 마지막 수정 2025-06-20.

현재 구현은 연구용 휴리스틱입니다. 환승·배차·공사비를 포함한 실제 운영 최적화와 전역 최적성 검증은 후속 과제입니다.

## 확인한 실행 범위

- 노트북 형식, 33개 셀 소스 보존, Python 구문 및 9개 연구 함수의 원본 일치를 확인했습니다.
- 실제 입력 엑셀 4개로 입력 검사와 후보 생성 3,000회·개선 10회·시드 42의 축소 실행을 완료했습니다. 9개 노선, 점수 계산, 로컬 PNG와 JSON 저장을 확인했습니다.
- 원본의 100,000회·10,000회 전체 실험과 외부 OSM 조회는 이번 저장소 정리 과정에서 재실행하지 않았습니다.
