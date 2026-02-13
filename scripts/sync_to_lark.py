"""
从notion表格获取数据, 解析并保存为本地csv，同时同步到飞书在线电子表格
"""
import os
from dotenv import load_dotenv
import requests
import csv
from typing import List, Dict, Any

load_dotenv()

def get_env(key: str):
    value = os.getenv(key)
    if not value:
        raise ValueError(f"{key}不存在，请检查.env文件")
    return value

# 获取环境变量
notion_token = get_env("NOTION_TOKEN")
notion_database_id = os.getenv("NOTION_PROJECTS_DATABASE_ID") or get_env("NOTION_DATABASE_ID")
lark_app_id = get_env("LARK_APP_ID")
lark_app_secret = get_env("LARK_APP_SECRET")
lark_sheet_token = get_env("LARK_SHEET_TOKEN")  # 电子表格token: MUQPsNc71hX0NJty5iOcf6d6nqd

def get_notion_data(token: str, database_id: str) -> list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    response = requests.post(url, headers=headers, json={})

    if response.status_code == 200:
        results = response.json().get("results", [])        
        props = [page.get("properties") for page in results]
        return props
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
        return []

def trans(props) -> list[dict]:
    rows = []
    for prop in props:
        row = {}
        
        # title
        title = prop.get('项目名称', {})
        title_list = title.get('title', []) if isinstance(title, dict) else []
        row['项目名称'] = title_list[0]['plain_text'] if title_list else ''
        
        # GitHub链接
        row['GitHub 链接'] = prop.get('GitHub 链接', {}).get('url', '')

        # 描述
        rich_text = prop.get('描述', {}).get('rich_text', [])
        row['描述'] = ''.join(i.get('plain_text', '') for i in rich_text)
        
        # Stars
        Stars = prop.get('Stars', {})
        Stars_list = Stars.get("rich_text", []) if isinstance(Stars, dict) else []
        row['Stars'] = Stars_list[0]['plain_text'] if Stars_list else ''
        
        # Stars_init
        row['Stars_list'] = prop.get('Stars_init', {}).get('number', '')
        
        # Forks
        row['Forks'] = prop.get('Forks', {}).get('number', '')
        
        # Watchers
        row['Wathers'] = prop.get('Wathers', {}).get('number', '')
        
        # Open Issues
        row['Open Issues'] = prop.get('Open Issues', {}).get('number', '')
        
        # 主要语言
        lang_dict = prop.get('主要语言', {}).get('select', {})
        row['主要语言'] = lang_dict.get('name', '') if isinstance(lang_dict, dict) else ''
        
        # 技术标签
        tags = prop.get('技术标签', {}).get('multi_select', [])
        row['技术标签'] = ', '.join(i.get('name', '') for i in tags)
        
        # 最后更新
        date_updated = prop.get('最后更新', {}).get('date', {})
        row['最后更新'] = date_updated.get('start', '')[:10] if date_updated else ''
        
        # 最后推送
        date_pushed = prop.get('最后推送', {}).get('date', {})
        row['最后推送'] = date_pushed.get('start', '')[:10] if date_pushed else ''
        
        # 作者
        rt_author = prop.get('作者', {}).get('rich_text', [])
        row['作者'] = ''.join(i.get('plain_text', '') for i in rt_author)
        
        # 许可证
        License = prop.get('许可证', {}).get('select', {})
        row['许可证'] = License.get('name', '') if isinstance(License, dict) else ''
        
        # 状态
        state = prop.get('状态', {}).get('select', {})
        row['状态'] = state.get('name', '') if isinstance(state, dict) else ''
        
        # 分类
        Class = prop.get('分类', {}).get('select', {})
        row['分类'] = Class.get('name', '') if isinstance(Class, dict) else ''
        
        rows.append(row)
    return rows

def save_to_csv(rows: list[dict], filepath = "notion_export.csv"):
    if not rows:
        print("没有数据")
        return
    
    fieldnames = list(rows[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"已保存 {len(rows)} 条数据到 {filepath}")

def get_lark_access_token() -> str:
    """获取飞书访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }
    data = {
        "app_id": lark_app_id,
        "app_secret": lark_app_secret
    }
    
    print("正在获取飞书访问令牌...")
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            access_token = result.get("tenant_access_token")
            print("✓ 成功获取访问令牌")
            return access_token
        else:
            raise Exception(f"获取access token失败: {result}")
    else:
        raise Exception(f"请求失败: {response.status_code}, {response.text}")

def get_sheet_info(access_token: str, sheet_token: str):
    """获取电子表格基本信息"""
    print("正在获取电子表格信息...")
    
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/metainfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            meta_info = result.get("data", {})
            print(f"表格标题: {meta_info.get('title', '未知')}")
            sheets = meta_info.get('sheets', [])
            print(f"工作表数量: {len(sheets)}")
            for sheet in sheets:
                sheet_id = sheet.get('sheetId', sheet.get('sheet_id', ''))
                print(f"  - {sheet.get('title')} (sheet_id: {sheet_id})")
            return sheets
        else:
            print(f"获取表格信息失败: {result}")
    else:
        print(f"获取表格信息请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")
    return []

def clear_lark_sheet(access_token: str, sheet_token: str, sheet_id: str = "0"):
    """清空飞书电子表格中的现有数据"""
    print("正在清空飞书电子表格数据...")
    
    # 先获取现有数据范围
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values_batch_get"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 获取较大的范围来检测数据
    params = {
        "ranges": [f"{sheet_id}!A1:Z1000"]
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            value_ranges = result.get("data", {}).get("valueRanges", [])
            if value_ranges:
                values = value_ranges[0].get("values", [])
                if values:
                    print(f"发现 {len(values)} 行数据")
                    # 清空数据 - 写入空值到整个范围
                    clear_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values"
                    clear_data = {
                        "valueRange": {
                            "range": f"{sheet_id}!A1:Z{len(values)}",
                            "values": [["" for _ in range(26)] for _ in range(len(values))]
                        }
                    }
                    
                    clear_response = requests.put(clear_url, headers=headers, json=clear_data)
                    if clear_response.status_code == 200:
                        clear_result = clear_response.json()
                        if clear_result.get("code") == 0:
                            print("✓ 成功清空电子表格数据")
                        else:
                            print(f"清空数据失败: {clear_result}")
                    else:
                        print(f"清空数据请求失败: {clear_response.status_code}")
                else:
                    print("电子表格已经是空的")
        else:
            print(f"获取表格数据失败: {result}")
    else:
        print(f"获取表格数据请求失败: {response.status_code}")

def sync_to_lark_sheet(rows: List[Dict[str, Any]], access_token: str, sheet_token: str, sheet_id: str = "0"):
    """将数据同步到飞书电子表格"""
    if not rows:
        print("没有数据需要同步")
        return
    
    print(f"正在同步 {len(rows)} 条记录到飞书电子表格...")
    
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 准备表头
    if not rows:
        return
        
    fieldnames = list(rows[0].keys())
    
    # 构造数据矩阵
    values = []
    # 添加表头
    values.append(fieldnames)
    
    # 添加数据行
    for row in rows:
        data_row = []
        for field in fieldnames:
            value = row.get(field, "")
            # 处理不同类型的数据
            if field in ['Stars_list', 'Forks', 'Wathers', 'Open Issues']:
                data_row.append(int(value) if value and str(value).isdigit() else "")
            else:
                data_row.append(str(value) if value else "")
        values.append(data_row)
    
    # 计算列字母
    end_column = chr(64 + min(len(fieldnames), 26))  # A-Z
    end_row = len(values)
    
    # 写入数据
    data = {
        "valueRange": {
            "range": f"{sheet_id}!A1:{end_column}{end_row}",
            "values": values
        }
    }
    
    print(f"正在写入数据到范围: {sheet_id}!A1:{end_column}{end_row}")
    response = requests.put(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        if result.get("code") == 0:
            print("✓ 成功同步数据到飞书电子表格")
        else:
            print(f"同步失败: {result}")
            print(f"请求数据: {data}")
    else:
        print(f"同步请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")
        print(f"请求数据: {data}")

def debug_sheet_operations(access_token: str, sheet_token: str, sheet_id: str):
    """调试电子表格操作"""
    print("\n=== 电子表格调试信息 ===")
    
    # 1. 检查表格是否存在和可访问
    meta_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/metainfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    print("1. 检查表格元信息...")
    meta_response = requests.get(meta_url, headers=headers)
    print(f"   状态码: {meta_response.status_code}")
    if meta_response.status_code == 200:
        meta_result = meta_response.json()
        print(f"   响应: {meta_result}")
        if meta_result.get("code") == 0:
            title = meta_result.get("data", {}).get("title", "未知")
            print(f"   ✓ 表格标题: {title}")
            
            # 显示实际的sheet信息
            sheets = meta_result.get("data", {}).get("sheets", [])
            print("   实际工作表信息:")
            for sheet in sheets:
                actual_sheet_id = sheet.get('sheetId', sheet.get('sheet_id', 'unknown'))
                print(f"     - {sheet.get('title')} (sheetId: {actual_sheet_id})")
        else:
            print(f"   ✗ 获取元信息失败: {meta_result}")
    else:
        print(f"   ✗ 请求失败: {meta_response.text}")
    
    # 2. 检查工作表是否存在
    print("\n2. 检查工作表...")
    sheets = get_sheet_info(access_token, sheet_token)
    if sheets:
        print(f"   ✓ 找到 {len(sheets)} 个工作表")
        for i, sheet in enumerate(sheets):
            actual_sheet_id = sheet.get('sheetId', sheet.get('sheet_id', ''))
            print(f"     {i+1}. {sheet.get('title')} (ID: {actual_sheet_id})")
    else:
        print("   ✗ 未找到工作表")
    
    # 3. 测试写入权限 - 写入测试数据
    print("\n3. 测试写入权限...")
    test_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values"
    test_data = {
        "valueRange": {
            "range": f"{sheet_id}!A1:B2",  # 使用传入的正确sheet_id
            "values": [
                ["测试字段1", "测试字段2"],
                ["测试值1", "测试值2"]
            ]
        }
    }
    
    test_response = requests.put(test_url, headers=headers, json=test_data)
    print(f"   写入测试状态码: {test_response.status_code}")
    if test_response.status_code == 200:
        test_result = test_response.json()
        print(f"   写入测试响应: {test_result}")
        if test_result.get("code") == 0:
            print("   ✓ 写入测试成功")
        else:
            print(f"   ✗ 写入测试失败: {test_result}")
    else:
        print(f"   ✗ 写入测试请求失败: {test_response.text}")
    
    # 4. 验证写入结果
    print("\n4. 验证写入结果...")
    read_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values_batch_get"
    read_params = {"ranges": [f"{sheet_id}!A1:B2"]}  # 使用传入的正确sheet_id
    read_response = requests.get(read_url, headers=headers, params=read_params)
    print(f"   读取测试状态码: {read_response.status_code}")
    if read_response.status_code == 200:
        read_result = read_response.json()
        print(f"   读取测试响应: {read_result}")
        if read_result.get("code") == 0:
            values = read_result.get("data", {}).get("valueRanges", [{}])[0].get("values", [])
            print(f"   读取到的数据: {values}")
        else:
            print(f"   ✗ 读取测试失败: {read_result}")
    else:
        print(f"   ✗ 读取测试请求失败: {read_response.text}")

def sync_to_lark_sheet_debug(rows: List[Dict[str, Any]], access_token: str, sheet_token: str, sheet_id: str = "0"):
    """带调试信息的数据同步函数"""
    if not rows:
        print("没有数据需要同步")
        return
    
    print(f"正在同步 {len(rows)} 条记录到飞书电子表格...")
    
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 准备表头
    if not rows:
        return
        
    fieldnames = list(rows[0].keys())
    print(f"字段列表: {fieldnames}")
    
    # 构造数据矩阵
    values = []
    # 添加表头
    values.append(fieldnames)
    
    # 添加数据行
    for i, row in enumerate(rows[:3]):  # 只显示前3行作为示例
        data_row = []
        for field in fieldnames:
            value = row.get(field, "")
            # 处理不同类型的数据
            if field in ['Stars_list', 'Forks', 'Wathers', 'Open Issues']:
                processed_value = int(value) if value and str(value).isdigit() else ""
            else:
                processed_value = str(value) if value else ""
            data_row.append(processed_value)
        values.append(data_row)
        print(f"第{i+1}行数据: {dict(zip(fieldnames, data_row))}")
    
    # 添加剩余行（不显示详细内容）
    for row in rows[3:]:
        data_row = []
        for field in fieldnames:
            value = row.get(field, "")
            if field in ['Stars_list', 'Forks', 'Wathers', 'Open Issues']:
                processed_value = int(value) if value and str(value).isdigit() else ""
            else:
                processed_value = str(value) if value else ""
            data_row.append(processed_value)
        values.append(data_row)
    
    # 计算列字母
    end_column = chr(64 + min(len(fieldnames), 26))  # A-Z
    end_row = len(values)
    
    print(f"\n准备写入的数据范围: {sheet_id}!A1:{end_column}{end_row}")
    print(f"数据矩阵大小: {len(values)} 行 × {len(fieldnames)} 列")
    
    # 显示前几行数据预览
    print("\n数据预览 (前5行):")
    for i, row in enumerate(values[:5]):
        print(f"  第{i+1}行: {row}")
    
    # 写入数据
    data = {
        "valueRange": {
            "range": f"{sheet_id}!A1:{end_column}{end_row}",
            "values": values
        }
    }
    
    print(f"\n正在执行写入操作...")
    response = requests.put(url, headers=headers, json=data)
    print(f"写入请求状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"写入响应: {result}")
        if result.get("code") == 0:
            print("✓ 成功同步数据到飞书电子表格")
            
            # 验证写入结果
            print("\n正在验证写入结果...")
            verify_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{sheet_token}/values_batch_get"
            verify_params = {"ranges": [f"{sheet_id}!A1:{end_column}{min(end_row, 10)}"]}  # 只验证前10行
            verify_response = requests.get(verify_url, headers=headers, params=verify_params)
            if verify_response.status_code == 200:
                verify_result = verify_response.json()
                if verify_result.get("code") == 0:
                    verified_values = verify_result.get("data", {}).get("valueRanges", [{}])[0].get("values", [])
                    print(f"验证读取到 {len(verified_values)} 行数据:")
                    for i, row in enumerate(verified_values[:3]):
                        print(f"  验证第{i+1}行: {row}")
                else:
                    print(f"验证读取失败: {verify_result}")
            else:
                print(f"验证读取请求失败: {verify_response.status_code}")
                
        else:
            print(f"同步失败: {result}")
            print(f"请求数据: {data}")
    else:
        print(f"同步请求失败: {response.status_code}")
        print(f"响应内容: {response.text}")
        print(f"请求数据: {data}")

def main():
    try:
        # 获取Notion数据
        print("正在获取Notion数据...")
        props = get_notion_data(notion_token, notion_database_id)
        rows = trans(props)
        
        if not rows:
            print("未获取到任何数据")
            return
        
        print(f"✓ 成功获取 {len(rows)} 条Notion数据")
        
        # 保存到CSV
        # save_to_csv(rows)
        
        # 获取飞书访问令牌
        access_token = get_lark_access_token()
        
        # 调试模式 - 先进行调试
        print("\n" + "="*50)
        print("开始调试模式...")
        debug_sheet_operations(access_token, lark_sheet_token, "951b55")  # 使用正确的sheet_id
        print("="*50 + "\n")
        
        # 获取表格信息
        sheets = get_sheet_info(access_token, lark_sheet_token)
        target_sheet_id = "951b55"  # 使用实际的sheet_id而不是默认的"0"
        if sheets:
            # 优先使用返回的实际sheet_id
            actual_sheet_id = sheets[0].get('sheetId', sheets[0].get('sheet_id', '951b55'))
            if actual_sheet_id:
                target_sheet_id = actual_sheet_id
            print(f"使用工作表: {sheets[0].get('title')} (ID: {target_sheet_id})")
        
        # 清空现有数据
        clear_lark_sheet(access_token, lark_sheet_token, target_sheet_id)
        
        # 同步新数据（使用调试版本）
        sync_to_lark_sheet_debug(rows, access_token, lark_sheet_token, target_sheet_id)
        
        print(f"\n🎉 数据同步完成！共处理 {len(rows)} 条记录")
        print(f"飞书电子表格链接: https://my.feishu.cn/sheets/{lark_sheet_token}")
        
    except Exception as e:
        print(f"❌ 执行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
