from dotenv import load_dotenv
import os
import requests
import json

# 加载环境变量
load_dotenv()

# 注意：这里使用 LARK_ 前缀，但你的.env文件可能使用的是 FEISHU_ 前缀
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")

def get_feishu_access_token() -> dict:
    """获取飞书访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    
    # 确保环境变量存在
    if not LARK_APP_ID or not LARK_APP_SECRET:
        print("环境变量缺失:")
        print(f"LARK_APP_ID/LARK_APP_ID: {LARK_APP_ID}")
        print(f"LARK_APP_SECRET/LARK_APP_SECRET: {LARK_APP_SECRET}")
        raise ValueError("请检查.env文件中的飞书应用配置")
    
    # 正确的请求格式
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }
    
    post_data = {
        "app_id": LARK_APP_ID,
        "app_secret": LARK_APP_SECRET
    }
    
    print(f"正在请求访问令牌...")
    print(f"App ID: {LARK_APP_ID[:10]}..." if LARK_APP_ID else "App ID 为空")
    
    try:
        response = requests.post(url, headers=headers, json=post_data)
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return {"error": f"HTTP {response.status_code}", "content": response.text}
            
    except Exception as e:
        print(f"请求异常: {e}")
        return {"error": str(e)}

def test_connection():
    """测试基本连接"""
    print("=== 飞书API连接测试 ===")
    
    # 测试基础连接
    test_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    try:
        response = requests.post(test_url, timeout=10)
        print(f"基础连接测试 - 状态码: {response.status_code}")
        if response.status_code == 400:
            print("✓ 基础连接正常，返回400是因为缺少参数")
        else:
            print(f"? 预期返回400，实际返回: {response.status_code}")
    except Exception as e:
        print(f"✗ 连接测试失败: {e}")

if __name__ == "__main__":
    # 先测试连接
    test_connection()
    print()
    
    # 获取访问令牌
    token_result = get_feishu_access_token()
    print("\n=== 访问令牌结果 ===")
    print(json.dumps(token_result, indent=2, ensure_ascii=False))