def get_clarity_summary(filepath="clarity_insights.txt"):
    """
    从手动总结的文件中获取Clarity数据摘要
    
    Args:
        filepath (str): Clarity洞察文件的路径
        
    Returns:
        str: 格式化的数据摘要
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"## Clarity洞察 (手动总结)\n{content}"
    except FileNotFoundError:
        return "## Clarity洞察 (手动总结)\n- 未找到Clarity洞察文件。"
    except Exception as e:
        return f"## Clarity洞察 (手动总结)\n- 读取文件失败: {str(e)}"

if __name__ == '__main__':
    # 创建一个示例文件来测试
    with open("clarity_insights.txt", "w", encoding="utf-8") as f:
        f.write("日期: 2023-10-28\n- 示例洞察1\n- 示例洞察2")
    print(get_clarity_summary()) 