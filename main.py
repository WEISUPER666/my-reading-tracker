from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from datetime import datetime, date
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import json
import hashlib

# ==========================================
# 1. 数据库基础配置 (SQLite)
# ==========================================
# 确保 data 目录存在
os.makedirs('data', exist_ok=True)
os.makedirs('data/covers', exist_ok=True)
# 数据库文件存储在 data 目录中，确保数据持久化
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/books.db"

# connect_args={"check_same_thread": False} 是 SQLite 搭配 FastAPI 时必须的设置
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建一个基础类，我们的表模型都要继承它
Base = declarative_base()

# ==========================================
# 2. 数据库表模型定义
# ==========================================
class Category(Base):
    """分类表 (Categories) - 独立管理分类"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # 分类名称，唯一
    icon = Column(String, nullable=True)  # 分类图标（Emoji 或图片 URL）
    created_at = Column(DateTime, default=datetime.now)


class Platform(Base):
    """平台表 (Platforms) - 独立管理来源平台"""
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # 平台名称，唯一
    created_at = Column(DateTime, default=datetime.now)


class Book(Base):
    """书籍表 (Books)"""
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, index=True, nullable=False) # 书名，设置 unique=True 防止重复
    cover = Column(String, nullable=True) # 封面预留，可以存图片的 URL 或路径
    category = Column(String, default="未分类") # 需求三：分类标签
    rating = Column(Integer, default=0) # 需求三：星级评分 0-5
    read_url = Column(String, nullable=True) # 需求一：直达阅读链接
    created_at = Column(DateTime, default=datetime.now) # 首次录入时间

    # 建立与"阅读记录"的关联。cascade 表示如果书被删了，相关的阅读记录也自动删除
    logs = relationship("ReadingLog", back_populates="book", cascade="all, delete-orphan")


class ReadingLog(Base):
    """阅读记录表 (Reading_Logs)"""
    __tablename__ = "reading_logs"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False) # 外键，关联书籍表
    platform = Column(String, nullable=False) # 来源平台 (如微信读书、喜马拉雅)
    status = Column(String, default="阅读中") # 状态：阅读中、已读完、已弃坑
    start_date = Column(DateTime, default=datetime.now) # 开始日期
    progress = Column(String, nullable=True) # 需求二：当前进度，如"第823章"或"50%"
    notes = Column(String, nullable=True) # 需求二：随手记，长文本备注

    # 建立与"书籍"的反向关联
    book = relationship("Book", back_populates="logs")


class SystemConfig(Base):
    """系统配置表 - 用于存储密码等安全配置"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=False)


# ==========================================
# 2.5 数据库迁移：自动检测并添加缺失列
# ==========================================
def upgrade_database():
    """检测旧表结构，自动添加缺失的列，避免"字段不存在"错误"""
    db = SessionLocal()
    try:
        # 检查 books 表是否有 category 列
        result = db.execute(text("PRAGMA table_info(books)")).fetchall()
        existing_columns = [row[1] for row in result]
        
        if 'category' not in existing_columns:
            db.execute(text("ALTER TABLE books ADD COLUMN category VARCHAR DEFAULT '未分类'"))
            print("[迁移] books 表添加 category 列")
        if 'rating' not in existing_columns:
            db.execute(text("ALTER TABLE books ADD COLUMN rating INTEGER DEFAULT 0"))
            print("[迁移] books 表添加 rating 列")
        if 'read_url' not in existing_columns:
            db.execute(text("ALTER TABLE books ADD COLUMN read_url VARCHAR"))
            print("[迁移] books 表添加 read_url 列")
        
        # 检查 reading_logs 表是否有 progress 和 notes 列
        result = db.execute(text("PRAGMA table_info(reading_logs)")).fetchall()
        existing_columns = [row[1] for row in result]
        
        if 'progress' not in existing_columns:
            db.execute(text("ALTER TABLE reading_logs ADD COLUMN progress VARCHAR"))
            print("[迁移] reading_logs 表添加 progress 列")
        if 'notes' not in existing_columns:
            db.execute(text("ALTER TABLE reading_logs ADD COLUMN notes VARCHAR"))
            print("[迁移] reading_logs 表添加 notes 列")
        
        # 检查 categories 表是否有 icon 列
        result = db.execute(text("PRAGMA table_info(categories)")).fetchall()
        existing_columns = [row[1] for row in result]
        
        if 'icon' not in existing_columns:
            db.execute(text("ALTER TABLE categories ADD COLUMN icon VARCHAR"))
            print("[迁移] categories 表添加 icon 列")

        db.commit()
        print("[迁移] 数据库结构检查完成")
    except Exception as e:
        print(f"[迁移] 数据库迁移过程出现异常: {e}")
        db.rollback()
    finally:
        db.close()


def seed_default_categories():
    """初始化默认分类，确保新用户也有分类可选"""
    db = SessionLocal()
    try:
        existing_count = db.query(Category).count()
        if existing_count == 0:
            default_categories = [
                ("小说", "📖"),
                ("历史", "📜"),
                ("科技", "💻"),
                ("哲学", "🧠"),
                ("心理学", "🧩"),
                ("经济管理", "📊"),
                ("个人成长", "🌱"),
                ("其他", "📂")
            ]
            for cat_name, cat_icon in default_categories:
                db.add(Category(name=cat_name, icon=cat_icon))
            db.commit()
            print(f"[初始化] 已添加 {len(default_categories)} 个默认分类")
    except Exception as e:
        print(f"[初始化] 添加默认分类时出错: {e}")
        db.rollback()
    finally:
        db.close()

def seed_default_platforms():
    """初始化默认平台，确保新用户也有平台可选"""
    db = SessionLocal()
    try:
        existing_count = db.query(Platform).count()
        if existing_count == 0:
            default_platforms = ["微信读书", "喜马拉雅", "本地文件", "实体书"]
            for plat_name in default_platforms:
                db.add(Platform(name=plat_name))
            db.commit()
            print(f"[初始化] 已添加 {len(default_platforms)} 个默认平台")
    except Exception as e:
        print(f"[初始化] 添加默认平台时出错: {e}")
        db.rollback()
    finally:
        db.close()


# 自动在数据库中创建所有表（如果表已经存在则不会重复创建）
Base.metadata.create_all(bind=engine)
# 执行数据库迁移（检测并添加缺失列）
upgrade_database()
# 初始化默认分类（仅首次运行时生效）
seed_default_categories()
# 初始化默认平台（仅首次运行时生效）
seed_default_platforms()


def init_admin_password():
    """初始化管理员密码：若数据库中不存在 admin_password，则使用 SHA-256 哈希存储默认密码 123456"""
    db = SessionLocal()
    try:
        existing = db.query(SystemConfig).filter(SystemConfig.key == "admin_password").first()
        if not existing:
            default_hash = hashlib.sha256("123456".encode()).hexdigest()
            db.add(SystemConfig(key="admin_password", value=default_hash))
            db.commit()
            print("[初始化] 已创建默认管理员密码（已哈希化）")
        else:
            print("[初始化] 管理员密码已存在，跳过初始化")
    except Exception as e:
        print(f"[初始化] 初始化管理员密码时出错: {e}")
        db.rollback()
    finally:
        db.close()


def get_admin_password_hash(db: Session) -> str:
    """从数据库获取当前管理员密码的哈希值"""
    config = db.query(SystemConfig).filter(SystemConfig.key == "admin_password").first()
    if config:
        return config.value
    return ""


# 初始化管理员密码
init_admin_password()

# ==========================================
# 3. FastAPI 应用实例初始化
# ==========================================
app = FastAPI(title="个人阅读档案 API", description="记录书籍与多次阅读/收听记录")

# 增加跨域配置，允许我们的前端页面访问后端 API
# 从环境变量 ALLOWED_ORIGINS 中读取允许的域名列表（逗号分隔），
# 未设置时使用安全的本地调试默认值
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
)
allow_origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有请求方法 (GET, POST 等)
    allow_headers=["*"],  # 允许所有请求头
)

# ==========================================
# 3.5 密码锁中间件 - 拦截所有 /api/ 请求
# ==========================================
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 只拦截 /api/ 开头的请求
    if request.url.path.startswith("/api/"):
        # 从请求头中获取 X-Auth-Token
        auth_token = request.headers.get("X-Auth-Token")
        
        # 从数据库读取密码哈希进行校验
        db = SessionLocal()
        try:
            stored_hash = get_admin_password_hash(db)
        finally:
            db.close()
        
        # 计算传入密码的哈希值进行比对
        if not auth_token or not stored_hash or hashlib.sha256(auth_token.encode()).hexdigest() != stored_hash:
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权访问，请提供正确的访问密码"}
            )
    
    response = await call_next(request)
    # 允许前端读取 X-Auth-Token 相关的错误信息
    response.headers["Access-Control-Expose-Headers"] = "*"
    return response

# 挂载静态文件目录，让 FastAPI 能够提供静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/covers", StaticFiles(directory="data/covers"), name="covers")

@app.get("/")
def read_root():
    """返回前端主页 index.html"""
    return FileResponse("index.html")

# ==========================================
# 4. 数据格式定义 (Pydantic Models) - 用于检查前端发来的数据
# ==========================================
class LogCreate(BaseModel):
    """当前端提交新的阅读记录时，我们规定它必须带有什么信息"""
    platform: str
    status: str = "阅读中"
    start_date: Optional[str] = None
    progress: Optional[str] = None  # 需求二：当前进度
    notes: Optional[str] = None     # 需求二：随手记

class LogUpdate(BaseModel):
    """更新阅读记录时允许的字段"""
    platform: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    progress: Optional[str] = None
    notes: Optional[str] = None

class BookCreate(BaseModel):
    """当前端提交新书时，必须带有书名和第一条阅读记录"""
    title: str
    cover: Optional[str] = None
    category: Optional[str] = "未分类"  # 需求三：分类标签
    rating: Optional[int] = 0           # 需求三：星级评分
    read_url: Optional[str] = None      # 需求一：直达阅读链接
    log: LogCreate

class BookUpdate(BaseModel):
    """编辑书籍时，允许更新书名、封面、分类、评分和阅读链接"""
    title: Optional[str] = None
    cover: Optional[str] = None
    category: Optional[str] = None   # 需求三：分类标签
    rating: Optional[int] = None     # 需求三：星级评分
    read_url: Optional[str] = None   # 需求一：直达阅读链接

class LogResponse(BaseModel):
    """阅读记录返回模型"""
    id: int
    book_id: int
    platform: str
    status: str
    start_date: datetime
    progress: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True

# ==========================================
# 5. 数据库工具函数
# ==========================================
def get_db():
    """每次收到请求时打开仓库大门，请求处理完关上大门"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 6. API 接口 (前端用来交互的通道 / 服务员)
# ==========================================

# ==========================================
# 6.1 分类管理 API
# ==========================================
class CategoryCreate(BaseModel):
    """创建分类的请求格式"""
    name: str
    icon: Optional[str] = None  # 分类图标（Emoji 或图片 URL）

@app.get("/api/categories/")
def get_categories(db: Session = Depends(get_db)):
    """获取所有分类列表"""
    categories = db.query(Category).order_by(Category.name).all()
    return [{"id": cat.id, "name": cat.name, "icon": cat.icon, "created_at": cat.created_at.strftime("%Y-%m-%d %H:%M:%S")} for cat in categories]

@app.post("/api/categories/")
def create_category(item: CategoryCreate, db: Session = Depends(get_db)):
    """创建新分类"""
    # 检查是否已存在同名分类
    existing = db.query(Category).filter(Category.name == item.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="分类名称已存在")
    db_cat = Category(name=item.name, icon=item.icon)
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return {"message": "分类创建成功", "id": db_cat.id, "name": db_cat.name, "icon": db_cat.icon}

class CategoryUpdate(BaseModel):
    """更新分类的请求格式"""
    name: Optional[str] = None
    icon: Optional[str] = None

@app.put("/api/categories/{category_id}")
def update_category(category_id: int, item: CategoryUpdate, db: Session = Depends(get_db)):
    """更新分类（名称、图标）"""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    if item.name is not None:
        # 检查新名称是否与其他分类重复
        existing = db.query(Category).filter(Category.name == item.name, Category.id != category_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="分类名称已存在")
        cat.name = item.name
    if item.icon is not None:
        cat.icon = item.icon
    db.commit()
    db.refresh(cat)
    return {"message": "分类更新成功", "id": cat.id, "name": cat.name, "icon": cat.icon}

@app.delete("/api/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """删除分类"""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    db.delete(cat)
    db.commit()
    return {"message": f"分类「{cat.name}」已删除"}

class PlatformCreate(BaseModel):
    """创建平台的请求格式"""
    name: str

@app.get("/api/platforms/")
def get_platforms(db: Session = Depends(get_db)):
    """获取所有平台列表"""
    platforms = db.query(Platform).order_by(Platform.name).all()
    return [{"id": plat.id, "name": plat.name, "created_at": plat.created_at.strftime("%Y-%m-%d %H:%M:%S")} for plat in platforms]

@app.post("/api/platforms/")
def create_platform(item: PlatformCreate, db: Session = Depends(get_db)):
    """创建新平台"""
    existing = db.query(Platform).filter(Platform.name == item.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="平台名称已存在")
    db_plat = Platform(name=item.name)
    db.add(db_plat)
    db.commit()
    db.refresh(db_plat)
    return {"message": "平台创建成功", "id": db_plat.id, "name": db_plat.name}

@app.delete("/api/platforms/{platform_id}")
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
    """删除平台"""
    plat = db.query(Platform).filter(Platform.id == platform_id).first()
    if not plat:
        raise HTTPException(status_code=404, detail="平台不存在")
    db.delete(plat)
    db.commit()
    return {"message": f"平台「{plat.name}」已删除"}


@app.get("/api/books/check")
def check_book(title: str, db: Session = Depends(get_db)):
    """【服务员1号】根据书名去仓库里找，看看这本书以前存过没有 (智能查重逻辑)"""
    book = db.query(Book).filter(Book.title == title).first()
    if book:
        # 如果找到了，告诉前端这本书的ID
        return {"exists": True, "book_id": book.id, "message": "此书已在书架中！"}
    return {"exists": False}

@app.post("/api/books/")
def create_book(item: BookCreate, db: Session = Depends(get_db)):
    """【服务员2号】录入一本全新的书，并顺便帮它登记第一次的阅读记录"""
    # 1. 存书籍表
    db_book = Book(
        title=item.title,
        cover=item.cover,
        category=item.category or "未分类",
        rating=item.rating or 0,
        read_url=item.read_url
    )
    db.add(db_book)
    db.commit() # 保存
    db.refresh(db_book)

    # 2. 存阅读记录表
    log_date = datetime.strptime(item.log.start_date, "%Y-%m-%d") if item.log.start_date else datetime.now()
    db_log = ReadingLog(
        book_id=db_book.id,
        platform=item.log.platform,
        status=item.log.status,
        start_date=log_date,
        progress=item.log.progress,  # 需求二
        notes=item.log.notes         # 需求二
    )
    db.add(db_log)
    db.commit() # 保存
    return {"message": "新书录入成功！", "book_id": db_book.id}

@app.post("/api/books/{book_id}/logs")
def add_reading_log(book_id: int, log: LogCreate, db: Session = Depends(get_db)):
    """【服务员3号】书已经有了(重刷)，只在原来书的下面增加一条阅读记录"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="找不到这本书")
        
    log_date = datetime.strptime(log.start_date, "%Y-%m-%d") if log.start_date else datetime.now()
    db_log = ReadingLog(
        book_id=book_id,
        platform=log.platform,
        status=log.status,
        start_date=log_date,
        progress=log.progress,  # 需求二
        notes=log.notes         # 需求二
    )
    db.add(db_log)
    db.commit()
    return {"message": "新增阅读记录成功！"}

@app.get("/api/books/")
def get_books(db: Session = Depends(get_db)):
    """【服务员4号】首页看板专用：去仓库里清点所有的书，算出每本书读了几次、最后一次是什么时候"""
    books = db.query(Book).all()
    result = []
    for book in books:
        # 把这本书所有的阅读记录都拿出来，按时间倒序排（最近的在最前）
        logs = db.query(ReadingLog).filter(ReadingLog.book_id == book.id).order_by(ReadingLog.start_date.desc()).all()
        result.append({
            "id": book.id,
            "title": book.title,
            "cover": book.cover, # 封面图片链接
            "category": book.category or "未分类",  # 需求三
            "rating": book.rating or 0,              # 需求三
            "read_url": book.read_url,               # 需求一：直达阅读链接
            "read_count": len(logs), # 算算总共有几条记录，这就是重刷次数
            "last_read_date": (logs[0].start_date if logs else book.created_at).strftime("%Y-%m-%d"),
            "status": logs[0].status if logs else "未知", # 取最后一次的状态
            "progress": logs[0].progress if logs else None,  # 需求二：最新进度
            "notes": logs[0].notes if logs else None         # 需求二：最新备注
        })
    # 把所有书按照"最后一次阅读时间"排个序
    result.sort(key=lambda x: x["last_read_date"], reverse=True)
    return result

@app.get("/api/books/{book_id}/logs")
def get_book_logs(book_id: int, db: Session = Depends(get_db)):
    """【服务员5号】当你点击某本书时，用时间轴的形式展示它所有的阅读记录"""
    logs = db.query(ReadingLog).filter(ReadingLog.book_id == book_id).order_by(ReadingLog.start_date.desc()).all()
    return [
        {
            "id": log.id,
            "book_id": log.book_id,
            "platform": log.platform,
            "status": log.status,
            "start_date": log.start_date,
            "progress": log.progress,
            "notes": log.notes
        }
        for log in logs
    ]

@app.put("/api/books/{book_id}")
def update_book(book_id: int, item: BookUpdate, db: Session = Depends(get_db)):
    """【服务员6号】更新指定书籍的 title、cover、category、rating、read_url"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="找不到这本书")
    
    if item.title is not None:
        # 检查新书名是否与其他书冲突
        existing = db.query(Book).filter(Book.title == item.title, Book.id != book_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="书名已存在，请使用其他名称")
        book.title = item.title
    
    if item.cover is not None:
        book.cover = item.cover
    
    if item.category is not None:
        book.category = item.category  # 需求三：更新分类
    
    if item.rating is not None:
        book.rating = max(0, min(5, item.rating))  # 需求三：更新评分，限制 0-5
    
    if item.read_url is not None:
        book.read_url = item.read_url  # 需求一：更新阅读链接
    
    db.commit()
    db.refresh(book)
    return {"message": "书籍信息更新成功！", "book_id": book.id}

@app.post("/api/upload/cover")
async def upload_cover(file: UploadFile = File(...)):
    """【服务员7号】接收封面图片，保存到 data/covers 目录，返回可访问的 URL 路径"""
    # 生成唯一文件名，避免重名
    ext = os.path.splitext(file.filename)[1] if '.' in file.filename else '.jpg'
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join("data/covers", unique_filename)
    
    # 保存文件（使用同步写入，避免额外依赖）
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {"url": f"/covers/{unique_filename}"}

@app.put("/api/logs/{log_id}")
def update_reading_log(log_id: int, item: LogUpdate, db: Session = Depends(get_db)):
    """【服务员8.5号】更新指定阅读记录的字段（平台、状态、日期、进度、备注）"""
    log = db.query(ReadingLog).filter(ReadingLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="找不到这条阅读记录")

    if item.platform is not None:
        log.platform = item.platform
    if item.status is not None:
        log.status = item.status
    if item.start_date is not None:
        log.start_date = datetime.strptime(item.start_date, "%Y-%m-%d")
    if item.progress is not None:
        log.progress = item.progress
    if item.notes is not None:
        log.notes = item.notes

    db.commit()
    db.refresh(log)
    return {"message": "阅读记录更新成功！"}

# ==========================================
# 需求二：快捷更新阅读进度（高频操作优化）
# ==========================================
class ProgressUpdate(BaseModel):
    """快速更新进度时只需要一个 progress 字段"""
    progress: str

@app.patch("/api/logs/{log_id}/progress")
def quick_update_progress(log_id: int, item: ProgressUpdate, db: Session = Depends(get_db)):
    """【服务员9号】专门用于快速更新单条阅读记录的进度，接收新的 progress 字符串并保存"""
    log = db.query(ReadingLog).filter(ReadingLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="找不到这条阅读记录")

    log.progress = item.progress
    db.commit()
    db.refresh(log)
    return {
        "message": "进度更新成功！",
        "log_id": log.id,
        "progress": log.progress
    }


@app.delete("/api/logs/{log_id}")
def delete_reading_log(log_id: int, db: Session = Depends(get_db)):
    """【服务员8号】删除一条阅读记录，如果一本书的所有记录都被删除，连同书籍一起删除"""
    # 查找阅读记录
    log = db.query(ReadingLog).filter(ReadingLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="找不到这条阅读记录")
    
    # 保存书籍 ID，用于后续检查
    book_id = log.book_id
    
    # 删除阅读记录
    db.delete(log)
    db.commit()
    
    # 检查这本书是否还有其他阅读记录
    remaining_logs = db.query(ReadingLog).filter(ReadingLog.book_id == book_id).count()
    
    # 如果没有其他记录，删除这本书
    if remaining_logs == 0:
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            # 清理孤儿封面图片：如果 book.cover 是本地路径，删除对应的图片文件
            if book.cover and book.cover.startswith("/covers/"):
                # 提取文件名并拼接实际路径：data/covers/文件名
                cover_filename = book.cover.lstrip("/")
                cover_path = os.path.join("data", cover_filename)
                try:
                    if os.path.exists(cover_path):
                        os.remove(cover_path)
                except Exception:
                    # 即使图片文件删除失败，也不影响数据库记录的正常删除
                    pass

            db.delete(book)
            db.commit()
            return {"message": "阅读记录删除成功，由于该书已无其他阅读记录，书籍也已删除"}
    
    return {"message": "阅读记录删除成功"}

# ==========================================
# 需求四：数据一键导出/导入接口
# ==========================================
@app.get("/api/export")
def export_data(db: Session = Depends(get_db)):
    """导出所有书籍和对应的阅读记录为完整的 JSON 结构"""
    books = db.query(Book).all()
    export_data = []
    
    for book in books:
        logs = db.query(ReadingLog).filter(ReadingLog.book_id == book.id).order_by(ReadingLog.start_date.asc()).all()
        
        book_data = {
            "id": book.id,
            "title": book.title,
            "cover": book.cover,
            "category": book.category or "未分类",
            "rating": book.rating or 0,
            "read_url": book.read_url,  # 需求一：导出阅读链接
            "created_at": book.created_at.strftime("%Y-%m-%d %H:%M:%S") if book.created_at else None,
            "reading_logs": [
                {
                    "id": log.id,
                    "platform": log.platform,
                    "status": log.status,
                    "start_date": log.start_date.strftime("%Y-%m-%d") if log.start_date else None,
                    "progress": log.progress,
                    "notes": log.notes
                }
                for log in logs
            ]
        }
        export_data.append(book_data)
    
    return {
        "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_books": len(export_data),
        "books": export_data
    }


@app.post("/api/import")
def import_data(data: dict, db: Session = Depends(get_db)):
    """导入备份数据：将 JSON 备份文件中的书籍和阅读记录恢复到数据库中"""
    books_data = data.get("books", [])
    if not books_data:
        raise HTTPException(status_code=400, detail="备份文件中没有找到书籍数据")
    
    imported_count = 0
    skipped_count = 0
    
    # 收集需要创建的新分类
    categories_to_create = set()
    for book_data in books_data:
        cat = book_data.get("category")
        if cat and cat != "未分类":
            categories_to_create.add(cat)
    
    # 自动创建缺失的分类
    for cat_name in categories_to_create:
        existing = db.query(Category).filter(Category.name == cat_name).first()
        if not existing:
            db.add(Category(name=cat_name))
    if categories_to_create:
        db.commit()
    
    for book_data in books_data:
        title = book_data.get("title")
        if not title:
            continue
        
        # 检查书名是否已存在（去重）
        existing = db.query(Book).filter(Book.title == title).first()
        if existing:
            skipped_count += 1
            continue
        
        # 创建书籍
        raw_rating = book_data.get("rating", 0)
        if raw_rating is None:
            raw_rating = 0
        safe_rating = max(0, min(5, int(raw_rating)))  # 限制评分范围 0-5
        
        raw_created_at = book_data.get("created_at")
        if raw_created_at and isinstance(raw_created_at, str):
            try:
                parsed_created_at = datetime.strptime(raw_created_at, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                parsed_created_at = datetime.now()
        else:
            parsed_created_at = datetime.now()
        
        db_book = Book(
            title=title,
            cover=book_data.get("cover"),
            category=book_data.get("category", "未分类"),
            rating=safe_rating,
            read_url=book_data.get("read_url"),  # 需求一：导入阅读链接
            created_at=parsed_created_at
        )
        db.add(db_book)
        db.flush()  # 获取 db_book.id
        
        # 创建阅读记录
        for log_data in book_data.get("reading_logs", []):
            raw_start_date = log_data.get("start_date")
            if raw_start_date and isinstance(raw_start_date, str):
                try:
                    log_date = datetime.strptime(raw_start_date, "%Y-%m-%d")
                except (ValueError, TypeError):
                    log_date = datetime.now()
            else:
                log_date = datetime.now()
            
            db_log = ReadingLog(
                book_id=db_book.id,
                platform=log_data.get("platform", "其他"),
                status=log_data.get("status", "阅读中"),
                start_date=log_date,
                progress=log_data.get("progress"),
                notes=log_data.get("notes")
            )
            db.add(db_log)
        
        imported_count += 1
    
    db.commit()
    
    return {
        "message": f"导入完成！成功导入 {imported_count} 本书",
        "imported_count": imported_count,
        "skipped_count": skipped_count
    }


# ==========================================
# 7. 系统设置 API（自定义系统名称、欢迎语、图标）
# ==========================================
class SystemSettingsUpdate(BaseModel):
    """更新系统设置的请求格式"""
    site_name: Optional[str] = None
    welcome_title: Optional[str] = None
    welcome_subtitle: Optional[str] = None
    site_icon: Optional[str] = None


def get_system_setting(db: Session, key: str, default: str = "") -> str:
    """从 system_config 表获取指定 key 的值，不存在则返回默认值"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        return config.value
    return default


def set_system_setting(db: Session, key: str, value: str):
    """设置或更新 system_config 表中的指定 key 的值"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        config.value = value
    else:
        db.add(SystemConfig(key=key, value=value))
    db.commit()


@app.get("/api/settings/")
def get_settings(db: Session = Depends(get_db)):
    """获取所有系统设置"""
    return {
        "site_name": get_system_setting(db, "site_name", "个人阅读档案"),
        "welcome_title": get_system_setting(db, "welcome_title", "欢迎回来，阅读者 👋"),
        "welcome_subtitle": get_system_setting(db, "welcome_subtitle", "今天又读了什么好书？赶快记录下你的阅读进度或听书历程吧。每一次记录都是灵魂的脚印。"),
        "site_icon": get_system_setting(db, "site_icon", ""),
    }


@app.post("/api/settings/")
def update_settings(item: SystemSettingsUpdate, db: Session = Depends(get_db)):
    """更新系统设置"""
    if item.site_name is not None:
        set_system_setting(db, "site_name", item.site_name)
    if item.welcome_title is not None:
        set_system_setting(db, "welcome_title", item.welcome_title)
    if item.welcome_subtitle is not None:
        set_system_setting(db, "welcome_subtitle", item.welcome_subtitle)
    if item.site_icon is not None:
        set_system_setting(db, "site_icon", item.site_icon)
    
    return {"message": "系统设置更新成功"}


# ==========================================
# 8. 修改访问密码 API
# ==========================================
class ChangePasswordRequest(BaseModel):
    """修改密码请求格式"""
    old_password: str
    new_password: str
    confirm_password: str


@app.post("/api/settings/change-password")
def change_password(item: ChangePasswordRequest, db: Session = Depends(get_db)):
    """修改管理员访问密码：验证旧密码哈希后，更新为新密码的哈希值"""
    # 1. 验证新密码与确认密码一致
    if item.new_password != item.confirm_password:
        raise HTTPException(status_code=400, detail="新密码与确认密码不一致")
    
    # 2. 验证新密码长度
    if len(item.new_password) < 4:
        raise HTTPException(status_code=400, detail="新密码长度不能少于 4 位")
    
    # 3. 从数据库获取当前密码哈希
    config = db.query(SystemConfig).filter(SystemConfig.key == "admin_password").first()
    if not config:
        raise HTTPException(status_code=500, detail="系统配置异常，未找到密码配置")
    
    # 4. 验证旧密码
    old_hash = hashlib.sha256(item.old_password.encode()).hexdigest()
    if config.value != old_hash:
        raise HTTPException(status_code=403, detail="原密码错误，请重试")
    
    # 5. 更新为新密码的哈希值
    new_hash = hashlib.sha256(item.new_password.encode()).hexdigest()
    config.value = new_hash
    db.commit()
    
    return {"message": "密码修改成功"}
