import csv
import tkinter as tk
from tkinter import filedialog, messagebox


def read_data():
    # 弹出文件选择对话框，限制只能选择 .csv 文件
    file_path = filedialog.askopenfilename(
        title="请选择 CSV 文件",
        filetypes=[("CSV 文件", "*.csv")]
    )

    # 如果用户没有选择文件，直接返回
    if not file_path:
        return

    try:
        # 清空文本框原有的内容
        text_box.delete("1.0", tk.END)

        # 读取选中的 CSV 文件
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                # 将每一行数据拼接成字符串，展示在界面文本框中
                text_box.insert(tk.END, ", ".join(row) + "\n")

    except Exception as e:
        messagebox.showerror("错误", f"读取文件失败: {e}")


# 创建主窗口
root = tk.Tk()
root.title("CSV 导入工具")
root.geometry("500x400")

# 创建“点击导入数据”按钮
btn = tk.Button(root, text="点击导入数据", command=read_data, font=("Arial", 12))
btn.pack(pady=10)

# 创建数据显示区域（带滚动条的文本框）
text_box = tk.Text(root, width=60, height=20)
text_box.pack(pady=10)

# 启动界面
root.mainloop()
