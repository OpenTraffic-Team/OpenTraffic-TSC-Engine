import redis
import json

import redis.exceptions
"""
@File      : redis_stream.py
@Desc      : redis工具
@Author    : lichenpu
@Date      : 2025-02-20
"""
class RedisStreamReader:
    def __init__(self, redis_host, redis_port, redis_password = None):
        """初始化方法
        
        Args:
            redis_host: redis地址
            redis_port: redis端口
        """ 
        self._host = redis_host
        self._port = redis_port
        self._pwd = redis_password
        self._clients_by_db = {}
        
    def _get_client(self, db):
        """创建多个redis实例
        
        Args:
            db: redis库
        """ 
        cli = self._clients_by_db.get(db)
        if cli is None:
            cli = redis.Redis(
                host=self._host,
                port=self._port,
                password=self._pwd,
                db=db,
                socket_connect_timeout=10,
                max_connections=5,     # 限制连接池大小
                decode_responses=False # 保持与你现有字节解码逻辑一致
            )
            self._clients_by_db[db] = cli
        return cli
    def getdata(self, redis_db, stream_key):
        client = self._get_client(redis_db)
        #key不存在就抛出异常
        if not client.exists(stream_key):
            raise KeyError(f"Stream key {stream_key} 不存在")
        #redis调用xread，从最新开始，每次读取1条数据，并且阻塞3秒
        latest_data = client.xread({stream_key: "0"}, count=1, block=3000)
        if latest_data:
            stream, entries = latest_data[0]  
            entry = entries[0] 
            entry_id, entry_data = entry
            #解码处理
            entry_data = self.decode_bytes_keys(entry_data) 
            state_data = json.loads(entry_data['data'])          
            return state_data
        else:
            return None
        
    def get_latest_data(self, redis_db, stream_key, count, stream_start="$"):
        """获取 Redis Stream 数据

        Args:
            redis_db: redis库
            stream_key: stream的key，如 origin_info_state:HHL_QHDD
            count: 读取条数
            stream_start: 读取起点，"$" 表示只取调用后新发布的数据，
                          "0" 表示从头读取已有数据（测试/回放场景）
        Returns:
            最新一条数据，或 None
        """
        client = self._get_client(redis_db)

        if not client.exists(stream_key):
            raise KeyError(f"Stream key {stream_key} 不存在")

        latest_data = client.xread({stream_key: stream_start}, count=count, block=3000)
        if latest_data:
            stream, entries = latest_data[0]
            entry_id, entry_data = entries[0]
            entry_data = self.decode_bytes_keys(entry_data)
            return json.loads(entry_data['data'])
        return None
        


            
    def push_data(self, redis_db, stream_key, data = None):
        try:
            """
            将数据推送到指定 Redis 数据库的 Stream。
            
            Args:
                redis_db: redis库
                stream_key: 推送相位数据到redis上的key
                data: 相位数据,需要是string类型
            Returns:
                返回steam存储id
            """
            if data is None:
            #TODO： 数据是空该返回什么
                pass
            client = self._get_client(redis_db)
            decorate_data = {"data":json.dumps(data, ensure_ascii=False)}    
            response = client.xadd(stream_key,  decorate_data, maxlen= 10000)
            return response
        except redis.exceptions.TimeoutError:
            print("Redis connection timeout")
    def get_value_by_key(self, redis_db, key):
        """根据key拿到redis数据
            
        Args:
            redis_db: redis库
            key: redis key
        Returns:
            value
        """
        try:       
            # 切换到指定的 Redis 数据库
            client = self._get_client(redis_db)

            # 获取指定键的值
            value = client.get(key)
            if value:
                return value.decode('utf-8')  # 解码为字符串
            else:
                print(f'调用redis的key错误')
                return None
        except redis.exceptions.TimeoutError:
            print("Redis connection timeout")
    
    def decode_bytes_keys(self, pending_dict):
        """
        递归地把字典中所有 bytes 类型的键解码成 str。
        如果值里也包含 bytes，可一并处理。
        Args:
            data: 需要处理的字典
        return:
            new_dict: 解码成str的字典
        """
        new_dict = {}
        for k, v in pending_dict.items():
            # 如果键是 bytes，则解码为 str
            if isinstance(k, bytes):
                k = k.decode('utf-8')
            
            # 如果值是字典，递归处理
            if isinstance(v, dict):
                v = self.decode_bytes_keys(v)
            # 如果值是 bytes 则解码
            elif isinstance(v, bytes):
                v = v.decode('utf-8')
            
            new_dict[k] = v
        return new_dict
    

    
    def close(self):
        try:
            for client in self._clients_by_db.values():
                try:
                    client.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"关闭 Redis 连接时出错：{e}")
    def get_stream_length(self, redis_db, stream_key):
        """
        获取指定 stream 的数据条数
        """
        client = self._get_client(redis_db)
        return client.xlen(stream_key)
    def get_neighbors_data(self, redis_db, stream_keys, count):
        """
        获取多个邻居路口的最近count条数据

        Args:
            redis_db: redis库
            stream_keys: list[str]，每个邻居路口的stream_key
            count: 每个邻居要获取多少条

        Returns:
            dict: {stream_key1: [data1, data2, ...], stream_key2: [...], ...}
        """
        client = self._get_client(redis_db)
        result = {}
        for key in stream_keys:
            if not client.exists(key):
                result[key] = []
                continue
            # 获取最新的count条
            entries = client.xrevrange(key, max='+', min='-', count=count)
            data_list = []
            for entry_id, entry_data in entries:
                entry_data = self.decode_bytes_keys(entry_data)
                state_data = json.loads(entry_data['data'])
                data_list.append(state_data)
            # 按时间正序排列
            data_list.reverse()
            result[key] = data_list
        return result