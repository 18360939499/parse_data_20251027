# 1. 从 flask 这个工具包里，导入 Flask 类
from flask import Flask

# 2. 创建一个 Flask 应用（等于启动一个网站）
# __name__ 是固定写法，让 Flask 知道自己在哪
app = Flask(__name__)

# 3. 装饰器：设置网址路径
# 访问 http://localhost:5000/ 时，执行下面的函数
@app.route('/')

# 4. 定义一个函数，处理访问请求
def hello():
    # 访问网站时，页面上显示这句话
    return "我是 Flask 做的后端接口！"

# 5. 主程序入口：只有直接运行这个文件时才执行
if __name__ == '__main__':
    # 6. 启动 Flask 网站服务器
    app.run()