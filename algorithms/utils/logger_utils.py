import io
import logging
import os
import logging
from datetime import datetime

class LogCollector:
    def __init__(self, enable_print=True):
        '''
        初始化日志工具
        
        Args：enable_print 日志同时打印
        '''
        #利用stringio存储日志
        self.log_buffer = io.StringIO()       
        self.logger = logging.getLogger('LogCollector')
        self.logger.setLevel(logging.DEBUG)

        # 创建一个 StreamHandler，将日志写入 log_buffer
        stream_handler = logging.StreamHandler(self.log_buffer)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)

        # 绑定 handler
        self.logger.addHandler(stream_handler)
        self.enable_print = enable_print

    def log(self, level, message):
        """获取发布的最新数据
               
        Args:
            level: 日志级别
            message: 日志信息
        """
        if level == logging.DEBUG:
            self.logger.debug(message)
        elif level == logging.INFO:
            self.logger.info(message)
        elif level == logging.WARNING:
            self.logger.warning(message)
        elif level == logging.ERROR:
            self.logger.error(message)
        elif level == logging.CRITICAL:
            self.logger.critical(message)

    def get_logs(self):
        """ 
        获取所有日志内容
        """
        return self.log_buffer.getvalue()

    def clear_logs(self):
        """ 
        清空日志   
        """
        self.log_buffer.truncate(0)
        self.log_buffer.seek(0)

    def save_latest_log(self, intersection):
        try:
            """
            将日志追加到 /log/ 目录，以 YYYY-MM-DD_{intersection_id}.log 命名
            每次存储一条新的日志。
            """
            log_dir = os.path.join(os.getcwd(), 'log')
            os.makedirs(log_dir, exist_ok=True)

            log_filename = f"{datetime.now().strftime('%Y-%m-%d')}_{intersection}.log"
            log_path = os.path.join(log_dir, log_filename)

            # 追加日志到文件
            with open(log_path, 'a', encoding='utf-8') as log_file:
                log_file.write(self.get_logs())

            # 清空日志缓存，防止重复写入
            self.clear_logs()
            return True, None
        except Exception as e:
            # 即使保存失败，也要清空日志缓存，防止内存泄漏
            error_msg = f"保存日志失败: {e}"
            print(error_msg)  # 打印到控制台
            
            # 将错误信息写入到日志缓存中
            self.log(logging.ERROR, error_msg)
            # 清空日志缓存
            self.clear_logs()
            # 返回错误信息，让调用方知道保存失败了
            return False, error_msg