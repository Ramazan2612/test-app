import subprocess
import requests
import json
import time
import os

# --- НАСТРОЙКИ ---
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:7b"  # Если будет сильно тормозить, поменяй на 1.5b
BRANCH = "main"
# ❗️ ЗАМЕНИ ЭТИ ДВЕ СТРОКИ НА СВОИ ДАННЫЕ:
REPO_OWNER = "Ramazan2612" 
REPO_NAME = "test-app"       

def ask_ollama(prompt):
    print("🤖 Думаю...")
    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()['response']
    except Exception as e:
        print(f"❌ Ошибка Ollama: {e}")
        return None

def get_latest_run_status():
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--limit", "1", "--json", "databaseId,status,conclusion"],
            capture_output=True, text=True, check=True
        )
        runs = json.loads(result.stdout)
        if not runs:
            return None, None
        run = runs[0]
        return run["databaseId"], run["conclusion"]
    except Exception as e:
        print(f"⚠️ Ошибка получения статуса: {e}")
        return None, None

def get_failed_log(run_id):
    print(f"📥 Скачиваю лог ошибки...")
    try:
        result = subprocess.run(
            ["gh", "run", "view", str(run_id), "--log-failed"],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except Exception as e:
        return str(e)

def main():
    print("🚀 Оркестратор запущен.")
    task = input("Введи задачу для ИИ: ")
    
    prompt = f"""
    Ты — senior Android-разработчик. Твоя задача: {task}.
    Отвечай ТОЛЬКО кодом файла. Без объяснений и markdown (без ```).
    В первой строке укажи имя файла в формате: // FILE: path/to/file.ext
    """
    
    code_response = ask_ollama(prompt)
    if not code_response:
        return

    lines = code_response.split('\n')
    file_path = "generated_file.txt" 
    if lines[0].startswith("// FILE:"):
        file_path = lines[0].replace("// FILE:", "").strip()
        code_response = '\n'.join(lines[1:])

    print(f"💾 Сохраняю в {file_path}...")
    os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(code_response)

    print("📤 Отправляю в GitHub...")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", f"Auto: {task[:30]}"], check=True)
    subprocess.run(["git", "push", "origin", BRANCH], check=True)

    print("⏳ Жду запуска GitHub Actions (30 сек)...")
    time.sleep(30) 
    
    run_id, conclusion = get_latest_run_status()
    if not run_id:
        print("❌ Запуск не найден.")
        return

    print(f"📊 Статус: {conclusion}")

    if conclusion == "failure":
        print("💥 Упало! Запрашиваю фикс...")
        log = get_failed_log(run_id)
        fix_prompt = f"Код упал. Лог:\n{log[-3000:]}\nИсправь. Верни ТОЛЬКО код с первой строкой // FILE: ..."
        fixed_code = ask_ollama(fix_prompt)
        if fixed_code:
            with open(file_path, 'w') as f:
                f.write('\n'.join(fixed_code.split('\n')[1:]))
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Auto-fix"], check=True)
            subprocess.run(["git", "push", "origin", BRANCH], check=True)
            print("✅ Фикс отправлен!")
    elif conclusion == "success":
        print("🎉 Успех! Сборка прошла.")
    else:
        print("⏳ Сборка идет. Проверь позже: gh run list")

if __name__ == "__main__":
    while True:
        try:
            print("\n" + "="*40)
            main()  # Запускаем одну итерацию (ввод задачи, генерация, пуш)
            print("="*40)
            print("✅ Готово! Введи новую задачу или нажми Ctrl+C для выхода.")
        except KeyboardInterrupt:
            print("\n👋 Выход из режима ИИ. До встречи!")
            break
        except Exception as e:
            print(f"\n❌ Произошла ошибка: {e}")
            print("🔄 Перезапуск цикла...")
            time.sleep(2)
