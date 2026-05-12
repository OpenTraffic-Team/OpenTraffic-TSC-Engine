import datetime
import sys
import os
import time
import hashlib
import base64

# 记录时间的隐藏文件路径（使用多个文件提高安全性）
# 所有文件都在 utils 目录下
BASE_DIR = os.path.dirname(__file__)
UTILS_DIR = os.path.join(BASE_DIR, "utils")  # 修复：应该是algorithms/utils，不是项目根目录/utils
TIME_RECORD_FILES = [
    os.path.join(UTILS_DIR, ".sys_info.bin"),           # 主文件
    os.path.join(UTILS_DIR, ".sys_backup.bin"),         # 备份文件1
    os.path.join(UTILS_DIR, ".cache_info.dat"),         # 备份文件2（伪装文件名）
]

# 尝试从编译的 .so 模块中读取嵌入的校验数据
_EMBEDDED_DATA = {}
def _get_embedded_license_data():
    """从编译的 .so 模块中获取嵌入的校验数据"""
    global _EMBEDDED_DATA
    if _EMBEDDED_DATA:
        return _EMBEDDED_DATA
    try:
        from algorithms.utils import license_data
        _EMBEDDED_DATA = {
            "sys_info": license_data.LICENSE_DATA.get("sys_info", ""),
            "sys_backup": license_data.LICENSE_DATA.get("sys_backup", ""),
            "cache_info": license_data.LICENSE_DATA.get("cache_info", ""),
        }
    except (ImportError, AttributeError):
        pass
    return _EMBEDDED_DATA

def _is_production_environment():
    """
    检测是否在生产环境中运行
    生产环境特征：utils目录下存在大量.so文件（编译后的模块）
    """
    try:
        # 检查 __file__ 是否是 .so 文件（最直接的判断）
        if __file__.endswith('.so'):
            return True
        
        # 检查 utils 目录下是否有 .so 文件（说明是打包后的环境）
        if os.path.exists(UTILS_DIR):
            so_files = [f for f in os.listdir(UTILS_DIR) if f.endswith('.so')]
            # 如果存在多个 .so 文件，认为是生产环境
            if len(so_files) >= 2:
                return True
    except:
        pass
    return False

# 加密密钥（使用文件路径的哈希值作为密钥的一部分，增加破解难度）
_ENCRYPTION_KEY = hashlib.sha256((BASE_DIR + "license_encryption_key_2024").encode()).digest()

def _encrypt_data(data):
    """加密数据"""
    try:
        # 使用XOR加密 + Base64编码
        data_bytes = data.encode('utf-8')
        encrypted = bytearray()
        key_len = len(_ENCRYPTION_KEY)
        for i, byte in enumerate(data_bytes):
            encrypted.append(byte ^ _ENCRYPTION_KEY[i % key_len])
        # Base64编码，使文件内容看起来像随机字符串
        return base64.b64encode(bytes(encrypted)).decode('utf-8')
    except Exception:
        return None

def _decrypt_data(encrypted_data):
    """解密数据"""
    try:
        # Base64解码
        encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
        # XOR解密
        decrypted = bytearray()
        key_len = len(_ENCRYPTION_KEY)
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ _ENCRYPTION_KEY[i % key_len])
        return bytes(decrypted).decode('utf-8')
    except Exception:
        return None

def _calculate_checksum(timestamp_str):
    """计算时间戳的校验和，用于检测文件是否被篡改"""
    # 使用简单的哈希算法生成校验码
    hash_obj = hashlib.md5((timestamp_str + "license_check_salt").encode())
    return hash_obj.hexdigest()[:8]  # 取前8位作为校验码

def _read_time_record(file_path):
    """读取时间记录文件，返回时间戳和校验码"""
    try:
        if not os.path.exists(file_path):
            return None, None
        with open(file_path, "r") as f:
            encrypted_content = f.read().strip()
            if not encrypted_content:
                return None, None
            
            # 尝试解密
            decrypted_content = _decrypt_data(encrypted_content)
            if decrypted_content is None:
                # 解密失败，可能是旧格式（未加密），尝试直接读取
                try:
                    # 兼容旧格式：timestamp:checksum 或 只有timestamp
                    parts = encrypted_content.split(":")
                    if len(parts) == 2:
                        return float(parts[0]), parts[1]
                    return float(encrypted_content), None
                except (ValueError, TypeError):
                    return None, None
            
            # 解密成功，解析格式：timestamp:checksum
            parts = decrypted_content.split(":")
            if len(parts) == 2:
                return float(parts[0]), parts[1]
            # 如果格式不对，返回None
            return None, None
    except (ValueError, IOError, OSError) as e:
        # 精确捕获异常类型，避免隐藏其他问题
        return None, None

def _write_time_record(file_path, timestamp, checksum, old_timestamp=None):
    """写入时间记录文件（加密存储）"""
    try:
        # 文件应该可以修改，用于记录每次运行的时间
        
        # 安全检查：如果提供了旧时间戳，新时间不能小于旧时间（防止回拨）
        if old_timestamp is not None and timestamp < old_timestamp:
            print(f" 警告：尝试写入的时间早于文件记录时间，拒绝更新")
            return
        
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 构造明文数据：timestamp:checksum
        plain_data = f"{timestamp}:{checksum}"
        
        # 加密数据
        encrypted_data = _encrypt_data(plain_data)
        if encrypted_data is None:
            # 加密失败，跳过
            return
        
        # 写入加密后的数据
        with open(file_path, "w") as f:
            f.write(encrypted_data)
        
        # 验证写入是否成功（读取并验证）
        try:
            verify_timestamp, verify_checksum = _read_time_record(file_path)
            if verify_timestamp is None or abs(verify_timestamp - timestamp) > 0.1:
                # 写入验证失败，可能是磁盘空间不足或权限问题
                print(f"⚠️  警告：文件写入验证失败：{os.path.basename(file_path)}")
        except:
            pass  # 验证失败不影响主流程
        
        # 注意：不再设置文件为只读，允许文件被更新
    except (IOError, OSError) as e:
        # 写入失败时，在关键场景（过期时）应该报错
        print(f" 警告：文件写入失败：{os.path.basename(file_path)}，错误：{str(e)}")
        # 注意：这里不抛出异常，因为可能只是部分文件写入失败

def _get_last_run_time():
    """从多个文件中读取最后运行时间，返回最晚的时间"""
    last_times = []
    missing_files = []
    embedded_data_used = False

    # 首先尝试从文件读取
    for file_path in TIME_RECORD_FILES:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
            continue

        timestamp, checksum = _read_time_record(file_path)
        if timestamp is not None:
            # 验证校验和
            if checksum is not None:
                expected_checksum = _calculate_checksum(str(timestamp))
                if checksum != expected_checksum:
                    # 校验和不匹配，文件可能被篡改
                    print(f"⚠️  警告：检测到时间记录文件异常，已忽略：{os.path.basename(file_path)}")
                    continue
            last_times.append((timestamp, file_path))

    # 如果所有文件都缺失，尝试从嵌入的 .so 模块中读取
    if missing_files and not last_times:
        embedded = _get_embedded_license_data()
        # 文件路径和嵌入数据的映射关系
        embedded_map = {
            ".sys_info.bin": "sys_info",
            ".sys_backup.bin": "sys_backup",
            ".cache_info.dat": "cache_info",
        }
        for file_path in TIME_RECORD_FILES:
            basename = os.path.basename(file_path)
            if basename in embedded_map:
                key = embedded_map[basename]
                if key in embedded and embedded[key]:
                    encrypted_content = embedded[key]
                    try:
                        decrypted_content = _decrypt_data(encrypted_content)
                        if decrypted_content:
                            parts = decrypted_content.split(":")
                            if len(parts) == 2:
                                timestamp = float(parts[0])
                                checksum = parts[1]
                                # 验证校验和
                                expected_checksum = _calculate_checksum(str(timestamp))
                                if checksum == expected_checksum:
                                    last_times.append((timestamp, file_path))
                                    embedded_data_used = True
                    except (ValueError, TypeError):
                        pass

    # 如果使用了嵌入数据，显示提示
    if embedded_data_used:
        print("ℹ️  信息：使用嵌入的校验数据（文件未找到）")

    # 生产环境必须存在时间记录文件，如果文件缺失且没有嵌入数据则报错
    if _is_production_environment() and missing_files and not embedded_data_used:
        print("\n" + "!"*60)
        print("❌ 安全错误：检测到时间记录文件缺失！")
        print("在生产环境中，以下文件必须存在：")
        for f in missing_files:
            print(f"  - {os.path.basename(f)}")
        print("系统已锁定，请联系开发者。")
        print("!"*60 + "\n")
        sys.exit(1)

    # 如果所有文件都读取失败
    if not last_times:
        # 情况1：文件缺失（生产环境必须报错，开发环境允许）
        # 这种情况已经在上面处理过了，这里不会执行到

        # 情况2：文件存在但解密失败（跨环境部署的正常情况，允许重新初始化）
        # 情况3：开发环境首次运行（允许）
        # 这两种情况都返回 None，允许重新初始化
        # 注意：如果是跨环境部署，文件会用新环境的密钥重新加密
        if _is_production_environment() and not missing_files:
            # 生产环境下文件存在但解密失败，说明是跨环境部署，允许重新初始化
            pass
        return None, None

    # 返回最晚的时间戳及其对应的文件路径
    latest = max(last_times, key=lambda x: x[0])
    return datetime.datetime.fromtimestamp(latest[0]), latest[1]

def verify_license(expired_date="2028-4-8"):
    """
    带防时钟回拨检查的授权系统（增强版）
    - 使用多个备份文件防止删除
    - 使用校验和防止文件被篡改
    - 精确的异常处理
    """
    current_time = datetime.datetime.now()
    try:
        expiry = datetime.datetime.strptime(expired_date, "%Y-%m-%d")
    except ValueError as e:
        print(f"❌ 授权配置错误：过期日期格式不正确")
        sys.exit(1)
    
    print(f"--- [安全系统] 正在校验授权... ---")

    # --- 逻辑核心：防回拨检查和过期状态检查 ---
    last_run_time, source_file = _get_last_run_time()
    
    if last_run_time is not None:
        # 关键检测1：如果文件记录时间 >= 过期时间，说明已经过期过，不允许运行（即使回拨时间）
        if last_run_time >= expiry:
            # 重要：即使检测1触发，也要确保文件记录的是过期后的时间
            # 防止在过期日期的00:00:00时，文件记录时间正好等于过期时间，但当前时间回拨后可以绕过
            if current_time > expiry:
                # 如果当前时间也超过过期时间，更新文件为当前时间（更晚的时间）
                timestamp_str = str(current_time.timestamp())
                checksum = _calculate_checksum(timestamp_str)
                old_timestamp = last_run_time.timestamp()
                for file_path in TIME_RECORD_FILES:
                    _write_time_record(file_path, current_time.timestamp(), checksum, old_timestamp)
            
            print("\n" + "!"*60)
            print("❌ 安全错误：算法已经过期，不允许运行！")
            print(f"文件记录时间：{last_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"过期时间：{expiry.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"当前系统时间：{current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("即使回拨系统时间也无法启动，请联系运维人员。")
            print("!"*60 + "\n")
            sys.exit(1)
        
        # 关键检测2：如果当前系统时间早于上次运行时间，说明时钟被恶意回拨
        # 使用 timedelta 进行精确比较，避免时区问题
        time_diff = (last_run_time - current_time).total_seconds()
        if time_diff > 0:
            # 时间回拨了，立即退出，不允许运行
            print("\n" + "!"*60)
            print("❌ 安全警告：检测到系统时钟异常（可能存在时间回拨）！")
            print(f"上次运行时间：{last_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"当前系统时间：{current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"时间回拨：{abs(time_diff):.0f} 秒")
            print("系统已锁定，请恢复正确的系统时间或联系开发者。")
            print("!"*60 + "\n")
            sys.exit(1)

    # --- 逻辑核心：到期检查 ---
    if current_time > expiry:
        # 当检测到当前时间超过过期时间时，统一提示"疑似过期"
        # 因为无法区分是正常过期还是系统时间被恶意向前调整
        # 重要：即使过期，也要更新文件为当前时间，标记为已过期，防止时间回拨后绕过检查
        timestamp_str = str(current_time.timestamp())
        checksum = _calculate_checksum(timestamp_str)
        # 获取旧时间戳，用于安全检查
        old_timestamp = last_run_time.timestamp() if last_run_time is not None else None
        for file_path in TIME_RECORD_FILES:
            _write_time_record(file_path, current_time.timestamp(), checksum, old_timestamp)
        
        print("\n" + "!"*60)
        print("❌ 您算法疑似已经过期，请联系运维人员")
        if last_run_time is None:
            print("提示：未检测到运行记录文件，可能是首次运行或文件被删除")
        else:
            print(f"提示：上次运行时间：{last_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"当前系统时间：{current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"过期日期：{expired_date}")
        print("!"*60 + "\n")
        sys.exit(1)

    # 校验通过，更新"最晚运行时间"记录到所有文件
    # 文件应该可以修改，用于记录每次运行的时间
    # 在更新时，会检查新时间不能小于旧时间（防止回拨）
    timestamp_str = str(current_time.timestamp())
    checksum = _calculate_checksum(timestamp_str)
    
    # 获取旧时间戳，用于安全检查
    old_timestamp = last_run_time.timestamp() if last_run_time is not None else None
    
    for file_path in TIME_RECORD_FILES:
        _write_time_record(file_path, current_time.timestamp(), checksum, old_timestamp)

    print("✅ 授权验证通过。")
    return True