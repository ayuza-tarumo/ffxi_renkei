import os
import json
from itertools import product
from collections import defaultdict
from flask import Flask, render_template, request

app = Flask(__name__)

# json file pathの定義
WEAPON_WS_FILE = os.path.join(app.root_path, 'weapon_ws_list.json')
WS_ATTR_FILE = os.path.join(app.root_path, 'ws_attr_list.json')
WEAPON_FILE = os.path.join(app.root_path, 'weapon_list.json')
RENKEI_PATTERN_FILE = os.path.join(app.root_path, 'renkei_pattern_list.json')
ATTR_LIST_FILE = os.path.join(app.root_path, 'attr_list.json')
# DATA_FILE = os.path.join(app.root_path, 'data.json')

def load_data_from_json(data_file):
    DATA_FILE = data_file
    if not os.path.exists(DATA_FILE):
        print(f"警告: データファイルが見つかりません: {DATA_FILE}")
        return None
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        print(f"エラー: JSONファイル{DATA_FILE}の読み込みに失敗しました: {e}")
        return None
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return None

# リストから辞書型へ変更する。同じ武器をキーとした辞書が作れないため
def build_selected_weapons_dict(selected_w, weapons_dict):
    counter = defaultdict(int)
    result = {}
    # print(f"test(sel_w) - {selected_w}")

    for key in selected_w:
        # 武器名は _? がついてるのでキーとして使うために削除
        key = key[:-2] if len(key) > 2 else key
        if key in weapons_dict:
            counter[key] += 1
            unique_key = f"{key}_{counter[key]}"
            result[unique_key] = weapons_dict[key]
    return result

def gen_weapon_comb(selected_weapons_dict, ws_attributes_dict, linkage_patterns):
    """
    weapons_dictの各キー（武器種）に対応するWSリストから、
    順序を保った全連携組み合わせ（1つずつ各武器種から選ぶ）を出力する。
    """
    # 辞書のキー順をリスト化（順序保持）
    weapon_order = list(selected_weapons_dict.keys())

    # 連携で使うWSリストを取得 [[トスWSリスト],[〆WSリスト]]
    renkei_ws_lists = [selected_weapons_dict[weapon] for weapon in weapon_order]
    
    result_list = []

    # すべての順序付きペアを生成。combo は(WS1, WS2, WS3, ...)のタプル
    for combo in product(*renkei_ws_lists):
        # 連携可否を評価
        attr_result = evaluate_chain(combo, ws_attributes_dict, linkage_patterns)

        # 連携が発生する (Noneじゃない) ものをWSと発生属性のリストへ追加
        if attr_result is not None:
            result_list.append(list(combo) + attr_result)
    
    return result_list

def evaluate_chain(ws_chain, ws_attributes_dict, linkage_patterns):
    """
    任意数のWSに対応した連携属性評価関数。
    Parameters:
        ws_chain: ["WS1", "WS2", "WS3", ...] のようなWS名リスト
        ws_attributes_dict: 各WSが持つ属性辞書
        linkage_patterns: (属性1, 属性2) → 連携属性 の辞書
    Returns:
        最後まで連携が成立すれば最終的な属性リスト、途中で途切れたら None。
    """
    if len(ws_chain) < 2:
        return None  # 2つ未満は評価できない

    # 最初の2WSで初期連携を生成
    current_attrs = []
    attrs1 = ws_attributes_dict.get(ws_chain[0], []) # トスの属性リスト 1個以上
    attrs2 = ws_attributes_dict.get(ws_chain[1], []) # 〆  の属性リスト 1個以上

    found = False # 連携属性が見つかるとTrueにすることで無効な組合せマッチを防止
    for a1 in attrs1:
        for a2 in attrs2:
            result = linkage_patterns.get((a1, a2)) # WS同士の属性で連携が発生するか？
            if result:
                current_attrs.append(result)
                found = True # 一度発生する組合せが見つかれば以降は評価せずループを抜ける。そのためのフラグ
                break
            if found:
                break

    if not current_attrs:
        return None  # 最初で不成立なら終了

    # 3つ目以降のWSを順に評価
    for i in range(2, len(ws_chain)):
        next_attrs = ws_attributes_dict.get(ws_chain[i], [])
        new_attrs = []
        found = False
        for prev in current_attrs:
            for next_attr in next_attrs:
                result = linkage_patterns.get((prev, next_attr))
                if result:
                    new_attrs.append(result)
                    found = True
                    break
                if found:
                    break

        if not new_attrs:
            return None  # 途中で不成立
        current_attrs = new_attrs  # 成立した連携属性を次に持ち越す

    return current_attrs  # 最終的に成立した属性

# 結果として表示する連携属性を指定する場合。複数指定可能
def select_param_attr():
    for index, item in enumerate(target_attr):
        print(f"{index+1} : {item}")
    user_input = input("input attr : ").strip()
    
    selected_indices = [int(num) - 1 for num in user_input.split()]
    selected_items = [target_attr[i] for i in selected_indices if 0 <= i < len(target_attr)]

    if not user_input:
        return []
    else:
        return selected_items

# 最終出力形式に変更    
def format_chain(lst):
    if not lst:
        return ""
    if len(lst) == 1:
        return f"({lst[0]})"
    return " → ".join(lst[:-1]) + f" ({lst[-1]})"

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_weapons = [] # 結果として欲しい武器。ユーザ選択
    selected_attr = [] # 結果として欲しい連携属性。ユーザ選択
    ws_attributes = []
    message = [] # エラーとか返したい文字列を入れる
    weapon_num = 4
    renkei_result = []
    weapon_list = load_data_from_json(WEAPON_FILE)    # 武器一覧
    weapon_dict = load_data_from_json(WEAPON_WS_FILE) # 武器-WSの辞書
    ws_attr_dict = load_data_from_json(WS_ATTR_FILE)  # WSと属性の全部セット
    renkei_patterns = load_data_from_json(RENKEI_PATTERN_FILE) # 連携パタンとその連携属性
    # 外部ファイルのJSONを都合に合わせて変換
    renkei_patterns = {tuple(key.split("+")): value for key, value in renkei_patterns.items()}

    # リクエストメソッドがPOSTの場合（フォームが送信されたとき）
    if request.method == 'POST':
        # フォームデータから 'weapon_select' の値を取得
        # HTMLの <select name="weapon_select"> に対応
        selected_weapons.append(request.form.get('weapon_select1'))
        selected_weapons.append(request.form.get('weapon_select2'))
        selected_weapons.append(request.form.get('weapon_select3'))
        selected_weapons.append(request.form.get('weapon_select4'))
        selected_attr = request.form.getlist('attr_checked')
        weapon_num = len(selected_weapons)
        # 選択された武器だけを含む辞書化
        selected_weapon_ws_dict = build_selected_weapons_dict(selected_weapons,weapon_dict)
        # 連携結果をリスト化 - WS1, WS2, ..., 属性
        renkei_result = gen_weapon_comb(selected_weapon_ws_dict, ws_attr_dict, renkei_patterns)
        # 属性を指定された場合、その結果だけにフィルタ
        if selected_attr:
            renkei_result = [rr for rr in renkei_result if any(k in rr[-1] for k in selected_attr)]
        # print(f"test(filterd) - {renkei_result}")

        # 文字列が空でない場合のみ後半2文字(例：格闘_x の _x 部分)を削り、選ばれた武器名だけのリストを作る
        selected_weapons = [text[:-2] if text else text for text in selected_weapons]
        selected_weapons = [item for item in selected_weapons if item] # 空の選択肢を削除
        if len(selected_weapons) < 2:
            print(f"武器は2つ以上指定して下さい")
            weapon_num = len(selected_weapons)
        renkei_result = [format_chain(r) for r in renkei_result]

    # GETリクエストの場合（初めてページにアクセスしたとき）
    # またはPOSTリクエスト処理後の結果を渡してテンプレートをレンダリング
    return render_template('index.html',
                           selected_weapon=selected_weapons,    # ユーザーが選択した武器名（あれば）
                           weapon_list=weapon_list,    # 武器一覧リスト
                           selected_attr=selected_attr,# 選択された属性リスト
                           renkei_result=renkei_result, # 連携結果一覧リスト
                           weapon_num=weapon_num)       # 選択された武器数

# アプリケーションを実行
if __name__ == '__main__':
    app.run(debug=True)