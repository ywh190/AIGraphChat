import requests
import re
import os

# 创建保存目录（如果不存在）
save_dir = r'E:\桌面\研究生毕业设计\spider'
os.makedirs(save_dir, exist_ok=True)

# href_list = []

# for i in range(1, 27):
#     # 注意：URL中有个空格，确认是否正确
#     url = f'https://www.zysj.com.cn/zhongyaocai/index__{i}.html'
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#     }
    
#     try:
#         response = requests.get(url, headers=headers, timeout=10)
#         response.encoding = 'utf-8'  # 设置编码
#         html = response.text
        
#         # 提取 href
#         hrefs = re.findall(r'<a href="(/zhongyaocai/[^"]+/index\.html)"', html)
#         href_list.extend(hrefs)
        
#         print(f"第 {i} 页抓取完成，获取 {len(hrefs)} 条链接")
        
#     except Exception as e:
#         print(f"第 {i} 页抓取失败: {e}")

# # 去重（如果需要）
# href_list = list(set(href_list))
# # 排序（可选）
# href_list.sort()

# print(f"\n总共获取 {len(href_list)} 条唯一链接")

# # 保存到文件
# save_path = os.path.join(save_dir, 'zysj_hrefs.txt')

# with open(save_path, 'w', encoding='utf-8') as f:
#     for href in href_list:
#         f.write(href + '\n')

# print(f"链接已保存到: {save_path}")

# # 同时保存完整URL（方便直接使用）
# full_urls = [f'https://www.zysj.com.cn{href}' for href in href_list]

# full_url_path = os.path.join(save_dir, 'zysj_full_urls.txt')
# with open(full_url_path, 'w', encoding='utf-8') as f:
#     for url in full_urls:
#         f.write(url + '\n')

# print(f"完整URL已保存到: {full_url_path}")

import requests
import re
import json
import os
import time
from bs4 import BeautifulSoup

class TCMScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
            'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Cookie':'Hm_lvt_dd26fe828fe48ed870036f7e81e58f9b=1770219769,1770219831,1770219950,1770219963; HMACCOUNT=220898E4A7E55141; Hm_lpvt_dd26fe828fe48ed870036f7e81e58f9b=1770220139',
            'Referer': 'https://www.zysj.com.cn/guji/index.html'
        }
        self.base_url = 'https://www.zysj.com.cn'
        
    def fetch_page(self, url):
        """获取页面内容"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            print(f"获取页面失败: {url}, 错误: {e}")
            return None
    
    def parse_herb_detail(self, html):
        """解析药材详细信息（兼容两种结构）"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 获取药材名称
        herb_name = soup.find('h1')
        name = herb_name.text.strip() if herb_name else ''
        
        herb_data = {
            '药材名称': name,
            'url': '',
            '来源信息': []
        }
        
        # 查找所有 section
        sections = soup.find_all('div', class_='section')
        
        for section in sections:
            # 尝试获取来源标题（h2）
            title = section.find('h2')
            
            if title:
                # 结构1：有h2标题（如《全国中草药汇编》：两面青）
                source_data = self.parse_section_with_title(section, title.text.strip())
            else:
                # 结构2：没有h2标题，从摘录字段获取来源
                source_data = self.parse_section_no_title(section)
            
            if source_data:
                herb_data['来源信息'].append(source_data)
        
        return herb_data
    
    def parse_section_with_title(self, section, title):
        """解析有标题的section（结构1）"""
        items = section.find_all('div', class_='item')
        data = {
            '来源': title,
        }
        
        for item in items:
            name_div = item.find('div', class_='item-name')
            content_div = item.find('div', class_='item-content')
            
            if name_div and content_div:
                field_name = name_div.text.strip()
                content = self.clean_text(content_div)
                data[field_name] = content
        
        return data
    
    def parse_section_no_title(self, section):
        """解析无标题的section（结构2）"""
        items = section.find_all('div', class_='item')
        data = {}
        
        for item in items:
            name_div = item.find('div', class_='item-name')
            content_div = item.find('div', class_='item-content')
            
            if name_div and content_div:
                field_name = name_div.text.strip()
                content = self.clean_text(content_div)
                data[field_name] = content
        
        # 尝试从"摘录"字段获取来源
        source = data.get('摘录', '未知来源')
        data['来源'] = source
        
        return data
    
    def clean_text(self, element):
        """清理文本，去除HTML标签但保留结构"""
        text = element.get_text(separator=' ', strip=True)
        text = ' '.join(text.split())
        return text
    
    def scrape_single(self, url):
        """爬取单个页面（用于测试）"""
        print(f"正在爬取: {url}")
        html = self.fetch_page(url)
        if html:
            return self.parse_herb_detail(html)
        return None
    
    def scrape_from_file(self, url_file_path, output_dir, start_index=0, end_index=None, auto_resume=True):
        """从URL列表文件批量爬取"""
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取URL列表
        with open(url_file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        # 自动检测上次的进度
        if auto_resume and start_index == 0:
            start_index = self.detect_last_progress(output_dir, len(urls))
        
        # 如果指定了结束索引，则使用指定范围，否则爬取从start_index到结尾的所有URL
        if end_index is not None:
            urls = urls[start_index:end_index]
        else:
            urls = urls[start_index:]
        
        all_herbs = []
        failed_urls = []
        
        for i, href in enumerate(urls, start_index + 1):
            if href.startswith('http'):
                full_url = href
            else:
                full_url = f"{self.base_url}{href}"
            
            print(f"[{i}/{len(urls) + start_index}] 正在爬取: {full_url}")
            
            html = self.fetch_page(full_url)
            if html:
                try:
                    herb_data = self.parse_herb_detail(html)
                    herb_data['url'] = full_url
                    all_herbs.append(herb_data)
                    print(f"  ✓ 成功: {herb_data['药材名称']} - {len(herb_data['来源信息'])}个来源")
                except Exception as e:
                    print(f"  ✗ 解析失败: {e}")
                    failed_urls.append(full_url)
            else:
                failed_urls.append(full_url)
            
            # 每10条保存一次，同时保存带起始索引的临时文件
            if i % 10 == 0:
                self.save_data(all_herbs, output_dir, f'herbs_temp_{i}.json')
            
            time.sleep(0.5)  # 礼貌延迟
        
        # 保存最终结果
        self.save_data(all_herbs, output_dir, 'all_herbs.json')
        self.save_to_csv(all_herbs, output_dir)
        
        # 保存失败的URL
        if failed_urls:
            with open(os.path.join(output_dir, 'failed_urls.txt'), 'w', encoding='utf-8') as f:
                for url in failed_urls:
                    f.write(url + '\n')
        
        print(f"\n爬取完成！成功: {len(all_herbs)}, 失败: {len(failed_urls)}")
        return all_herbs
    
    def detect_last_progress(self, output_dir, total_urls):
        """自动检测上次的进度"""
        import glob
        import re
        
        # 查找所有临时文件
        temp_files = glob.glob(os.path.join(output_dir, 'herbs_temp_*.json'))
        
        if not temp_files:
            print("未找到之前的进度文件，从头开始爬取")
            return 0
        
        # 找到最大的索引号
        max_index = 0
        for file_path in temp_files:
            filename = os.path.basename(file_path)
            match = re.search(r'herbs_temp_(\d+)\.json', filename)
            if match:
                index = int(match.group(1))
                max_index = max(max_index, index)
        
        # 为了安全起见，从最后保存的位置往前回退一点，避免丢失数据
        resume_index = max(0, max_index - 10)
        print(f"检测到之前进度，从索引 {resume_index} 开始继续爬取")
        return resume_index
    
    def save_data(self, data, output_dir, filename):
        """保存为JSON"""
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"数据已保存: {filepath}")
    
    def save_to_csv(self, data, output_dir):
        """保存为CSV格式（便于Excel查看）"""
        import csv
        
        filepath = os.path.join(output_dir, 'all_herbs.csv')
        
        # 收集所有可能的字段
        all_fields = set()
        for herb in data:
            for source in herb.get('来源信息', []):
                all_fields.update(source.keys())
        
        # 确保关键字段在前
        priority_fields = ['药材名称', 'URL', '来源', '拼音注音', '别名', '性味', '功能主治', '用法用量']
        other_fields = sorted([f for f in all_fields if f not in priority_fields])
        all_fields_ordered = priority_fields + other_fields
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(all_fields_ordered)
            
            for herb in data:
                base_info = {
                    '药材名称': herb['药材名称'],
                    'URL': herb['url']
                }
                for source in herb.get('来源信息', []):
                    row_dict = {**base_info, **source}
                    row = [row_dict.get(field, '') for field in all_fields_ordered]
                    writer.writerow(row)
        
        print(f"CSV已保存: {filepath}")


# ==================== 测试和运行 ====================

if __name__ == '__main__':
    scraper = TCMScraper()

    print("\n" + "=" * 50)
    print("开始批量爬取...")
    print("=" * 50)
    
    url_file = r'E:\桌面\研究生毕业设计\spider\zysj_hrefs.txt'
    output_dir = r'E:\桌面\研究生毕业设计\spider\herb_details'
    
    # 自动检测上次的进度并从中断处继续爬取
    # 如果想从特定位置开始，可以设置 start_index 参数，例如 start_index=7650
    herbs = scraper.scrape_from_file(url_file, output_dir, start_index=0, end_index=None, auto_resume=True)