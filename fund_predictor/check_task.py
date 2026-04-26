import requests
import json

task_id = "train_018956_dbea74e098"
task_resp = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
task_data = task_resp.json().get("data", {})
print(f"任务状态: {task_data.get('status')}")
print(f"进度: {task_data.get('progress')}%")
print(f"阶段: {task_data.get('stage')}")
print(f"消息: {task_data.get('message')}")
