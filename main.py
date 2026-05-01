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
import base64
import httpx
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 环境变量（使用脚本所在目录的绝对路径，确保 uvicorn reload 时也能正确加载）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

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

def search_book_cover(title: str) -> Optional[str]:
    """
    根据书名自动搜索封面图片 URL。
    优先使用 OpenLibrary Search API，如果失败则尝试 Google Books API。
    返回封面 URL 字符串，搜索不到则返回 None。
    """
    # --- 方案一：OpenLibrary Search API（免费、无需认证） ---
    try:
        resp = httpx.get(
            "https://openlibrary.org/search.json",
            params={"title": title, "limit": 1},
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": "MyReadingTracker/1.0"}
        )
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("docs", [])
            if docs and docs[0].get("cover_i"):
                cover_id = docs[0]["cover_i"]
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                # 验证封面图片是否可访问
                try:
                    head_resp = httpx.head(cover_url, timeout=5.0, follow_redirects=True)
                    if head_resp.status_code == 200:
                        print(f"[封面搜索] OpenLibrary 找到封面: {cover_url}")
                        return cover_url
                except Exception:
                    pass
    except Exception as e:
        print(f"[封面搜索] OpenLibrary 请求失败: {e}")

    # --- 方案二：Google Books API（免费、无需认证） ---
    try:
        resp = httpx.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": title, "maxResults": 1},
            timeout=8.0,
            follow_redirects=True
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                image_links = items[0].get("volumeInfo", {}).get("imageLinks", {})
                cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
                if cover_url:
                    # Google Books 返回 http，升级为 https
                    cover_url = cover_url.replace("http://", "https://")
                    print(f"[封面搜索] Google Books 找到封面: {cover_url}")
                    return cover_url
    except Exception as e:
        print(f"[封面搜索] Google Books 请求失败: {e}")

    print(f"[封面搜索] 未找到「{title}」的封面")
    return None


@app.post("/api/books/")
def create_book(item: BookCreate, db: Session = Depends(get_db)):
    """【服务员2号】录入一本全新的书，并顺便帮它登记第一次的阅读记录"""
    # 1. 存书籍表
    # 如果用户没有手动提供封面，则自动搜索
    cover_url = item.cover
    if not cover_url:
        cover_url = search_book_cover(item.title)

    db_book = Book(
        title=item.title,
        cover=cover_url,
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
        # 空字符串表示清空链接，None 表示不修改
        book.read_url = item.read_url if item.read_url else None  # 需求一：更新阅读链接
    
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
    """导出所有书籍和对应的阅读记录为完整的 JSON 结构，本地封面图片转为 base64 嵌入"""
    books = db.query(Book).all()
    export_data = []
    
    for book in books:
        logs = db.query(ReadingLog).filter(ReadingLog.book_id == book.id).order_by(ReadingLog.start_date.asc()).all()
        
        # 处理封面：如果是本地上传的图片，转为 base64 嵌入
        cover_value = book.cover
        if cover_value and cover_value.startswith("/covers/"):
            # 提取文件名并拼接实际路径
            cover_filename = cover_value.lstrip("/")
            cover_path = os.path.join("data", cover_filename)
            try:
                if os.path.exists(cover_path):
                    with open(cover_path, "rb") as f:
                        cover_bytes = f.read()
                    # 获取文件扩展名确定 MIME 类型
                    ext = os.path.splitext(cover_filename)[1].lower()
                    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
                    mime_type = mime_map.get(ext, "image/jpeg")
                    cover_value = f"data:{mime_type};base64,{base64.b64encode(cover_bytes).decode('utf-8')}"
                    print(f"[导出] 已将本地封面 {cover_filename} 转为 base64")
            except Exception as e:
                print(f"[导出] 读取封面文件失败: {e}")
                # 读取失败则保留原始路径
        
        book_data = {
            "id": book.id,
            "title": book.title,
            "cover": cover_value,
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
    
    # 收集需要创建的新平台（从阅读记录中提取）
    platforms_to_create = set()
    for book_data in books_data:
        for log_data in book_data.get("reading_logs", []):
            plat = log_data.get("platform")
            if plat:
                platforms_to_create.add(plat)
    
    # 自动创建缺失的平台
    for plat_name in platforms_to_create:
        existing = db.query(Platform).filter(Platform.name == plat_name).first()
        if not existing:
            db.add(Platform(name=plat_name))
    if platforms_to_create:
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
        
        # 处理封面：如果是 base64 数据，还原为本地文件
        cover_value = book_data.get("cover")
        if cover_value and cover_value.startswith("data:"):
            try:
                # 解析 data:image/jpeg;base64,xxxx 格式
                header, b64_data = cover_value.split(",", 1)
                # 从 MIME 类型推断扩展名
                mime_type = header.split(";")[0].split(":")[1] if ":" in header else "image/jpeg"
                ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
                ext = ext_map.get(mime_type, ".jpg")
                # 保存为本地文件
                unique_filename = f"{uuid.uuid4().hex}{ext}"
                file_path = os.path.join("data/covers", unique_filename)
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                cover_value = f"/covers/{unique_filename}"
                print(f"[导入] 已将 base64 封面还原为本地文件: {unique_filename}")
            except Exception as e:
                print(f"[导入] base64 封面还原失败: {e}")
                cover_value = None  # 还原失败则不设置封面
        
        db_book = Book(
            title=title,
            cover=cover_value,
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
    # AI 配置字段
    ai_api_key: Optional[str] = None
    ai_base_url: Optional[str] = None
    ai_model_name: Optional[str] = None


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
        # AI 配置（API Key 脱敏返回，不暴露完整密钥）
        "ai_api_key_set": bool(get_system_setting(db, "ai_api_key", "")),
        "ai_base_url": get_system_setting(db, "ai_base_url", os.getenv("AI_BASE_URL", "https://api.deepseek.com")),
        "ai_model_name": get_system_setting(db, "ai_model_name", os.getenv("AI_MODEL_NAME", "deepseek-chat")),
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
    # AI 配置
    if item.ai_api_key is not None:
        set_system_setting(db, "ai_api_key", item.ai_api_key)
    if item.ai_base_url is not None:
        set_system_setting(db, "ai_base_url", item.ai_base_url)
    if item.ai_model_name is not None:
        set_system_setting(db, "ai_model_name", item.ai_model_name)
    
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


# ==========================================
# 9. AI 阅读助手 API（支持 Function Calling）
# ==========================================
class ChatRequest(BaseModel):
    """AI 聊天请求格式"""
    message: str
    history: Optional[List[dict]] = []  # 聊天历史记录 [{role, content}]


# AI 系统提示词：定义助手的角色和行为
AI_SYSTEM_PROMPT = """你是一个专业的"AI 阅读助手"，专门帮助用户管理个人阅读档案。
你的职责包括：
1. 推荐书籍：根据用户的兴趣、阅读历史推荐合适的书籍
2. 阅读建议：帮助用户制定阅读计划、提供阅读方法建议
3. 书籍讨论：与用户讨论已读书籍的内容、感悟
4. 阅读统计分析：帮助用户分析阅读习惯和偏好
5. 解答疑问：回答与阅读、书籍相关的问题
6. 更新进度：当用户要求更新某本书的阅读进度时，调用 update_book_progress 工具
7. 添加新书：当用户提到要添加新书、录入新书、开始读一本新书时，调用 add_new_book 工具直接为用户创建新书档案

【上下文关联规则 - 非常重要】
当用户的消息中没有明确提到书名时（例如"我又看了5回"、"更新一下进度"、"读到第100章了"等），
你必须从对话历史中推断用户指的是哪本书。具体策略：
- 优先查找对话中最近一次提到的书名（例如用户之前说"我刚更新完《红楼梦》"，紧接着说"我又看了5回"，则书名应为"红楼梦"）
- 如果对话历史中也没有明确书名，则在调用 update_book_progress 工具时将 book_title 留空，系统会自动尝试匹配或提示用户确认
- 绝对不要在用户没有指明书名的情况下随意猜测一个书名

请用友好、专业的语气回复，回复内容简洁明了，适合在聊天窗口中阅读。
如果用户询问与阅读无关的问题，礼貌地引导回阅读相关话题。"""


# 定义 AI 可调用的工具列表（Function Calling Tools）
AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_book_progress",
            "description": "更新指定书籍的阅读进度。当用户提到要更新某本书的进度、记录读到第几章、标记为已读完等操作时调用此工具。如果用户没有指明书名，可以从对话历史中推断；如果无法推断，book_title 留空，系统会自动匹配最近更新的书籍。",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_title": {
                        "type": "string",
                        "description": "书籍的名称（支持模糊匹配，例如用户说'三体'可以匹配到'三体全集'）。如果用户未指明书名且无法从上下文推断，可留空或传空字符串。"
                    },
                    "new_progress": {
                        "type": "string",
                        "description": "新的阅读进度文本，例如'第50章'、'50%'、'已读完'、'第3章第12节'等"
                    }
                },
                "required": ["new_progress"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_new_book",
            "description": "为用户添加一本新书到阅读档案中。当用户提到要添加新书、录入新书、开始读一本新书等操作时调用此工具。如果书名已存在则不会重复添加。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "书籍的名称，例如'三体'、'百年孤独'等"
                    },
                    "author": {
                        "type": "string",
                        "description": "书籍的作者，例如'刘慈欣'、'马尔克斯'等（可选）"
                    },
                    "total_chapters": {
                        "type": "string",
                        "description": "书籍的总回数或章节数，例如'100章'、'30回'等（可选）"
                    },
                    "current_progress": {
                        "type": "string",
                        "description": "用户当前的阅读进度，例如'第1章'、'刚开始'等（可选）"
                    }
                },
                "required": ["title"]
            }
        }
    }
]


def execute_update_book_progress(book_title: str, new_progress: str) -> str:
    """
    执行更新书籍进度的内部函数。
    1. 如果提供了书名，模糊匹配书名
    2. 如果未提供书名，自动查找最近更新过进度的书籍
    3. 找到该书最新的阅读记录
    4. 更新其进度字段
    返回执行结果的文本描述。
    """
    db = SessionLocal()
    try:
        matched_book = None

        if book_title and book_title.strip():
            # 有明确书名：模糊匹配书名（使用 LIKE 进行模糊搜索）
            matched_book = db.query(Book).filter(Book.title.like(f"%{book_title}%")).first()
            if not matched_book:
                return f"未找到包含「{book_title}」的书籍，请检查书名是否正确。"
        else:
            # 未提供书名：查找最近有阅读记录更新的书籍
            # 通过 ReadingLog 的 start_date 倒序找到最近活跃的书籍
            latest_log_with_book = (
                db.query(ReadingLog, Book)
                .join(Book, ReadingLog.book_id == Book.id)
                .order_by(ReadingLog.start_date.desc())
                .first()
            )
            if latest_log_with_book:
                matched_book = latest_log_with_book[1]
            else:
                # 如果没有任何阅读记录，尝试查找最近添加的书籍
                matched_book = db.query(Book).order_by(Book.created_at.desc()).first()

            if not matched_book:
                return "书架中暂无任何书籍，请先添加一本书籍后再更新进度。"

        # 找到该书最新的阅读记录（按开始日期倒序）
        latest_log = (
            db.query(ReadingLog)
            .filter(ReadingLog.book_id == matched_book.id)
            .order_by(ReadingLog.start_date.desc())
            .first()
        )

        if not latest_log:
            return f"找到了书籍「{matched_book.title}」，但该书没有阅读记录，请先在系统中添加阅读记录。"

        # 更新进度
        latest_log.progress = new_progress
        db.commit()

        # 如果是自动匹配的（用户未指定书名），在返回信息中明确告知
        if not book_title or not book_title.strip():
            return f"成功更新！已自动匹配到最近活跃的书籍「{matched_book.title}」，阅读进度已更新为「{new_progress}」。"
        else:
            return f"成功更新！书籍「{matched_book.title}」的最新阅读记录进度已更新为「{new_progress}」。"

    except Exception as e:
        db.rollback()
        return f"更新进度时发生错误：{str(e)}"
    finally:
        db.close()


def execute_add_new_book(title: str, author: str = "", total_chapters: str = "", current_progress: str = "") -> str:
    """
    执行添加新书的内部函数。
    1. 检查数据库中是否已有同名书籍
    2. 如果已存在，提示用户并返回
    3. 如果不存在，创建新书记录（自动搜索封面）
    返回执行结果的文本描述。
    """
    db = SessionLocal()
    try:
        # 检查是否已有同名书籍（精确匹配）
        existing_book = db.query(Book).filter(Book.title == title).first()
        if existing_book:
            return f"书架中已存在书籍「{title}」（ID: {existing_book.id}），无需重复添加。如需更新进度，请使用更新进度功能。"

        # 构建备注信息（将 author、total_chapters 等可选信息写入备注）
        notes_parts = []
        if author:
            notes_parts.append(f"作者：{author}")
        if total_chapters:
            notes_parts.append(f"总章节数：{total_chapters}")
        notes = "；".join(notes_parts) if notes_parts else None

        # 自动搜索封面
        cover_url = search_book_cover(title)

        # 创建新书记录
        db_book = Book(
            title=title,
            cover=cover_url,
            category="未分类",
            rating=0
        )
        db.add(db_book)
        db.commit()
        db.refresh(db_book)

        # 创建初始阅读记录
        db_log = ReadingLog(
            book_id=db_book.id,
            platform="其他",
            status="阅读中",
            start_date=datetime.now(),
            progress=current_progress if current_progress else None,
            notes=notes
        )
        db.add(db_log)
        db.commit()

        result_msg = f"成功添加新书「{title}」（ID: {db_book.id}）。"
        if cover_url:
            result_msg += f" 已自动获取封面。"
        else:
            result_msg += f" 未找到封面，保留默认状态。"
        if author:
            result_msg += f" 作者：{author}。"
        if total_chapters:
            result_msg += f" 共{total_chapters}。"
        if current_progress:
            result_msg += f" 当前进度：{current_progress}。"
        return result_msg

    except Exception as e:
        db.rollback()
        return f"添加新书时发生错误：{str(e)}"
    finally:
        db.close()


@app.post("/api/chat")
def chat_with_ai(item: ChatRequest):
    """AI 阅读助手聊天接口：支持 Function Calling，可调用后端工具执行操作"""
    # 优先从数据库读取 AI 配置，未设置时回退到环境变量
    db = SessionLocal()
    try:
        db_api_key = get_system_setting(db, "ai_api_key", "")
        db_base_url = get_system_setting(db, "ai_base_url", "")
        db_model_name = get_system_setting(db, "ai_model_name", "")
    finally:
        db.close()

    api_key = db_api_key if db_api_key else os.getenv("AI_API_KEY", "")
    base_url = db_base_url if db_base_url else os.getenv("AI_BASE_URL", "https://api.deepseek.com")
    model_name = db_model_name if db_model_name else os.getenv("AI_MODEL_NAME", "deepseek-chat")

    if not api_key or api_key == "your_api_key_here":
        raise HTTPException(
            status_code=500,
            detail="AI 服务未配置：请在系统设置中配置 AI API Key，或在 .env 文件中设置 AI_API_KEY"
        )

    try:
        # 初始化 OpenAI 客户端（兼容 DeepSeek 等 OpenAI 格式的服务）
        client = OpenAI(api_key=api_key, base_url=base_url)

        # 构建消息列表：系统提示 + 历史记录 + 当前用户消息
        messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]

        # 添加历史对话记录（最多保留最近 20 条消息）
        if item.history:
            messages.extend(item.history[-20:])

        # 添加当前用户消息
        messages.append({"role": "user", "content": item.message})

        # 第一次调用大模型 API（携带工具定义）
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=AI_TOOLS,
            tool_choice="auto",  # 让模型自动决定是否需要调用工具
            temperature=0.7,
            max_tokens=1024,
        )

        assistant_message = response.choices[0].message

        # 检查 AI 是否请求调用工具
        data_updated = False  # 标记是否有数据变更，供前端判断是否需要刷新书架

        if assistant_message.tool_calls:
            # 将 AI 的回复（包含 tool_calls）添加到消息列表
            messages.append(assistant_message)

            # 逐个处理工具调用
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                print(f"[AI Agent] 调用工具: {function_name}, 参数: {function_args}")

                # 根据函数名分发执行
                if function_name == "update_book_progress":
                    result = execute_update_book_progress(
                        book_title=function_args.get("book_title", ""),
                        new_progress=function_args.get("new_progress", "")
                    )
                elif function_name == "add_new_book":
                    result = execute_add_new_book(
                        title=function_args.get("title", ""),
                        author=function_args.get("author", ""),
                        total_chapters=function_args.get("total_chapters", ""),
                        current_progress=function_args.get("current_progress", "")
                    )
                else:
                    result = f"未知的工具: {function_name}"

                print(f"[AI Agent] 工具执行结果: {result}")

                # 判断工具是否执行成功（结果以"成功"开头表示操作成功）
                if result.startswith("成功"):
                    data_updated = True

                # 将工具执行结果添加到消息列表
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

            # 第二次调用大模型 API，让 AI 根据工具执行结果生成最终回复
            second_response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )

            ai_reply = second_response.choices[0].message.content
        else:
            # AI 没有请求调用工具，直接返回文本回复
            ai_reply = assistant_message.content

        return {"reply": ai_reply, "data_updated": data_updated}

    except Exception as e:
        print(f"[AI 聊天] 调用失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI 服务调用失败：{str(e)}"
        )
