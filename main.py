from fastapi import FastAPI, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func as sqlfunc
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_settings import BaseSettings
from datetime import datetime, timedelta
from typing import Optional, List, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from io import BytesIO, StringIO
import enum, json, csv, pandas as pd, os

# ─── SETTINGS ────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    APP_NAME: str = "Yegassi API"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite:///./yegassi.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: str = '["*"]'
    ADMIN_EMAIL: str = "admin@yegassi.cm"
    ADMIN_PASSWORD: str = "Admin123!"

    def get_cors_origins(self):
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return ["*"]

    class Config:
        env_file = ".env"

settings = Settings()

# ─── DATABASE ─────────────────────────────────────────────────────────────────

DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── ENUMS ───────────────────────────────────────────────────────────────────

class RegionCameroun(str, enum.Enum):
    CENTRE       = "Centre"
    LITTORAL     = "Littoral"
    OUEST        = "Ouest"
    NORD_OUEST   = "Nord-Ouest"
    SUD_OUEST    = "Sud-Ouest"
    SUD          = "Sud"
    EST          = "Est"
    ADAMAOUA     = "Adamaoua"
    NORD         = "Nord"
    EXTREME_NORD = "Extrême-Nord"

class TrancheDAge(str, enum.Enum):
    QUINZE_DIX_SEPT          = "15-17"
    DIX_HUIT_VINGT_QUATRE    = "18-24"
    VINGT_CINQ_TRENTE_QUATRE = "25-34"
    TRENTE_CINQ_PLUS         = "35+"

class Genre(str, enum.Enum):
    HOMME      = "Homme"
    FEMME      = "Femme"
    AUTRE      = "Autre"
    NON_PRECISE = "Non précisé"

class NiveauEtude(str, enum.Enum):
    PRIMAIRE   = "Primaire"
    SECONDAIRE = "Secondaire"
    SUPERIEUR  = "Supérieur"
    AUCUN      = "Aucun"

class MotivationUsage(str, enum.Enum):
    COMMUNICATION  = "Communication"
    DIVERTISSEMENT = "Divertissement"
    INFORMATION    = "Information / Actualités"
    ETUDES         = "Études / Tutoriels"
    BUSINESS       = "Business / Commerce"
    AUTRE          = "Autre"

# ─── MODELS ──────────────────────────────────────────────────────────────────

from sqlalchemy import Enum as SAEnum

class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    nom             = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    est_admin       = Column(Boolean, default=False)
    est_actif       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=sqlfunc.now())
    reponses        = relationship("Reponse", back_populates="collecteur")

class Reponse(Base):
    __tablename__ = "reponses"
    id                    = Column(Integer, primary_key=True, index=True)
    region                = Column(SAEnum(RegionCameroun), nullable=False, index=True)
    ville                 = Column(String(100), nullable=True)
    tranche_age           = Column(SAEnum(TrancheDAge), nullable=False, index=True)
    genre                 = Column(SAEnum(Genre), nullable=False, index=True)
    niveau_etude          = Column(SAEnum(NiveauEtude), nullable=False)
    situation_pro         = Column(String(100), nullable=True)
    utilise_whatsapp      = Column(Boolean, default=False)
    utilise_facebook      = Column(Boolean, default=False)
    utilise_tiktok        = Column(Boolean, default=False)
    utilise_instagram     = Column(Boolean, default=False)
    utilise_youtube       = Column(Boolean, default=False)
    utilise_linkedin      = Column(Boolean, default=False)
    utilise_messenger     = Column(Boolean, default=False)
    utilise_twitter       = Column(Boolean, default=False)
    utilise_snapchat      = Column(Boolean, default=False)
    autres_plateformes    = Column(String(255), nullable=True)
    heures_par_jour       = Column(Float, nullable=False)
    plateforme_principale = Column(String(50), nullable=True)
    motivation_principale = Column(SAEnum(MotivationUsage), nullable=False)
    motivations_secondaires = Column(JSON, nullable=True)
    achat_en_ligne        = Column(Boolean, default=False)
    partage_contenu       = Column(Boolean, default=False)
    suivi_actualites      = Column(Boolean, default=False)
    usage_professionnel   = Column(Boolean, default=False)
    impact_bien_etre      = Column(Integer, nullable=True)
    commentaire_libre     = Column(Text, nullable=True)
    collecteur_id         = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    source                = Column(String(50), default="formulaire")
    created_at            = Column(DateTime(timezone=True), server_default=sqlfunc.now(), index=True)
    collecteur            = relationship("Utilisateur", back_populates="reponses")

class ImportLog(Base):
    __tablename__ = "import_logs"
    id           = Column(Integer, primary_key=True, index=True)
    nom_fichier  = Column(String(255), nullable=False)
    nb_lignes    = Column(Integer, default=0)
    nb_erreurs   = Column(Integer, default=0)
    statut       = Column(String(20), default="en_cours")
    details      = Column(JSON, nullable=True)
    importeur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=sqlfunc.now())

# ─── SECURITY ─────────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Utilisateur:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide ou expiré", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise exc
    except JWTError:
        raise exc
    user = db.query(Utilisateur).filter(Utilisateur.email == email).first()
    if user is None or not user.est_actif:
        raise exc
    return user

def get_admin_user(current_user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not current_user.est_admin:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return current_user

# ─── SCHEMAS ─────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UtilisateurCreate(BaseModel):
    email: EmailStr
    nom: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6)
    est_admin: bool = False

class UtilisateurOut(BaseModel):
    id: int; email: str; nom: str; est_admin: bool; est_actif: bool; created_at: datetime
    class Config: from_attributes = True

class ReponseCreate(BaseModel):
    region: RegionCameroun
    ville: Optional[str] = None
    tranche_age: TrancheDAge
    genre: Genre
    niveau_etude: NiveauEtude
    situation_pro: Optional[str] = None
    utilise_whatsapp: bool = False
    utilise_facebook: bool = False
    utilise_tiktok: bool = False
    utilise_instagram: bool = False
    utilise_youtube: bool = False
    utilise_linkedin: bool = False
    utilise_messenger: bool = False
    utilise_twitter: bool = False
    utilise_snapchat: bool = False
    autres_plateformes: Optional[str] = None
    plateforme_principale: Optional[str] = None
    heures_par_jour: float = Field(..., ge=0, le=24)
    motivation_principale: MotivationUsage
    motivations_secondaires: Optional[List[str]] = None
    achat_en_ligne: bool = False
    partage_contenu: bool = False
    suivi_actualites: bool = False
    usage_professionnel: bool = False
    impact_bien_etre: Optional[int] = Field(None, ge=1, le=5)
    commentaire_libre: Optional[str] = None

class ReponseOut(ReponseCreate):
    id: int; source: str; created_at: datetime; collecteur_id: Optional[int] = None
    class Config: from_attributes = True

class ReponsePaginated(BaseModel):
    total: int; page: int; per_page: int; items: List[ReponseOut]

class StatPlateforme(BaseModel):
    plateforme: str; count: int; pourcentage: float

class DashboardStats(BaseModel):
    total_reponses: int
    moy_heures_jour: float
    region_top: str
    plateforme_top: str
    plateformes: List[StatPlateforme]
    regions: List[dict]
    tranches_age: List[dict]
    genres: List[dict]
    motivations: List[dict]
    bien_etre_moyen: Optional[float]
    reponses_par_jour: List[dict]

# ─── APP STARTUP ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(Utilisateur).filter(Utilisateur.est_admin == True).first():
            db.add(Utilisateur(
                email=settings.ADMIN_EMAIL, nom="Administrateur Yegassi",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                est_admin=True, est_actif=True,
            ))
            db.commit()
            print(f"✅ Admin créé : {settings.ADMIN_EMAIL}")
    finally:
        db.close()
    yield

app = FastAPI(title="Yegassi API 🇨🇲", version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ─── ROUTES : SANTÉ ──────────────────────────────────────────────────────────

@app.get("/health", tags=["Santé"])
def health():
    return {"status": "ok"}

@app.get("/api", tags=["Santé"])
def racine():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "✅ En ligne", "docs": "/docs"}

# ─── FRONTEND STATIQUE ───────────────────────────────────────────────────────

import os
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def serve_frontend():
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "✅ En ligne", "docs": "/docs"}

# ─── ROUTES : AUTH ───────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=Token, tags=["Auth"])
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.est_actif:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    return {"access_token": create_access_token({"sub": user.email}), "token_type": "bearer"}

@app.get("/auth/me", response_model=UtilisateurOut, tags=["Auth"])
def me(current_user: Utilisateur = Depends(get_current_user)):
    return current_user

@app.post("/auth/register", response_model=UtilisateurOut, status_code=201, tags=["Auth"])
def register(data: UtilisateurCreate, db: Session = Depends(get_db), _: Utilisateur = Depends(get_admin_user)):
    if db.query(Utilisateur).filter(Utilisateur.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = Utilisateur(email=data.email, nom=data.nom, hashed_password=hash_password(data.password), est_admin=data.est_admin)
    db.add(user); db.commit(); db.refresh(user)
    return user

# ─── ROUTES : RÉPONSES ───────────────────────────────────────────────────────

@app.post("/reponses/", response_model=ReponseOut, status_code=201, tags=["Réponses"])
def soumettre_reponse(data: ReponseCreate, db: Session = Depends(get_db), current_user: Utilisateur = Depends(get_current_user)):
    r = Reponse(**data.model_dump(), collecteur_id=current_user.id, source="formulaire")
    db.add(r); db.commit(); db.refresh(r)
    return r

@app.get("/reponses/", response_model=ReponsePaginated, tags=["Réponses"])
def lister_reponses(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    region: Optional[str] = None, tranche_age: Optional[str] = None, genre: Optional[str] = None,
    db: Session = Depends(get_db), _: Utilisateur = Depends(get_current_user)):
    q = db.query(Reponse)
    if region: q = q.filter(Reponse.region == region)
    if tranche_age: q = q.filter(Reponse.tranche_age == tranche_age)
    if genre: q = q.filter(Reponse.genre == genre)
    total = q.count()
    items = q.order_by(Reponse.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "page": page, "per_page": per_page, "items": items}

@app.delete("/reponses/{reponse_id}", status_code=204, tags=["Réponses"])
def supprimer_reponse(reponse_id: int, db: Session = Depends(get_db), admin: Utilisateur = Depends(get_admin_user)):
    r = db.query(Reponse).filter(Reponse.id == reponse_id).first()
    if not r: raise HTTPException(status_code=404, detail="Réponse introuvable")
    db.delete(r); db.commit()

# ─── ROUTES : ANALYTICS ──────────────────────────────────────────────────────

def _pct(part, total): return round((part/total*100), 1) if total else 0.0

@app.get("/analytics/dashboard", response_model=DashboardStats, tags=["Analytics"])
def dashboard(db: Session = Depends(get_db), _: Utilisateur = Depends(get_current_user)):
    total = db.query(func.count(Reponse.id)).scalar() or 0
    moy_heures = db.query(func.avg(Reponse.heures_par_jour)).scalar() or 0.0
    bien_etre_moyen = db.query(func.avg(Reponse.impact_bien_etre)).scalar()

    plat_fields = {"WhatsApp": Reponse.utilise_whatsapp, "Facebook": Reponse.utilise_facebook,
        "TikTok": Reponse.utilise_tiktok, "Instagram": Reponse.utilise_instagram,
        "YouTube": Reponse.utilise_youtube, "LinkedIn": Reponse.utilise_linkedin,
        "Messenger": Reponse.utilise_messenger, "X (Twitter)": Reponse.utilise_twitter, "Snapchat": Reponse.utilise_snapchat}
    plateformes = sorted([StatPlateforme(plateforme=n, count=(db.query(func.count(Reponse.id)).filter(f==True).scalar() or 0),
        pourcentage=_pct(db.query(func.count(Reponse.id)).filter(f==True).scalar() or 0, total))
        for n, f in plat_fields.items()], key=lambda x: x.count, reverse=True)

    regions_raw = db.query(Reponse.region, func.count(Reponse.id).label("cnt"), func.avg(Reponse.heures_par_jour).label("moy")).group_by(Reponse.region).order_by(func.count(Reponse.id).desc()).all()
    regions = [{"region": r.region.value if hasattr(r.region,"value") else str(r.region), "count": r.cnt, "moy_heures": round(float(r.moy or 0),2), "pourcentage": _pct(r.cnt, total)} for r in regions_raw]

    age_raw = db.query(Reponse.tranche_age, func.count(Reponse.id).label("cnt")).group_by(Reponse.tranche_age).order_by(func.count(Reponse.id).desc()).all()
    tranches_age = [{"tranche": r.tranche_age.value if hasattr(r.tranche_age,"value") else str(r.tranche_age), "count": r.cnt, "pourcentage": _pct(r.cnt, total)} for r in age_raw]

    genre_raw = db.query(Reponse.genre, func.count(Reponse.id).label("cnt")).group_by(Reponse.genre).order_by(func.count(Reponse.id).desc()).all()
    genres = [{"genre": r.genre.value if hasattr(r.genre,"value") else str(r.genre), "count": r.cnt, "pourcentage": _pct(r.cnt, total)} for r in genre_raw]

    motiv_raw = db.query(Reponse.motivation_principale, func.count(Reponse.id).label("cnt")).group_by(Reponse.motivation_principale).order_by(func.count(Reponse.id).desc()).all()
    motivations = [{"motivation": r.motivation_principale.value if hasattr(r.motivation_principale,"value") else str(r.motivation_principale), "count": r.cnt, "pourcentage": _pct(r.cnt, total)} for r in motiv_raw]

    try:
        db_url = settings.DATABASE_URL or ""
        if "sqlite" in db_url:
            from sqlalchemy import text as sa_text
            rows = db.execute(sa_text("SELECT strftime('%Y-%m-%d', created_at) as d, count(*) as cnt FROM reponses GROUP BY d ORDER BY d DESC LIMIT 30")).fetchall()
        else:
            from sqlalchemy import text as sa_text
            rows = db.execute(sa_text("SELECT created_at::date as d, count(*) as cnt FROM reponses GROUP BY d ORDER BY d DESC LIMIT 30")).fetchall()
        reponses_par_jour = [{"date": str(r[0]), "count": r[1]} for r in rows]
    except Exception:
        reponses_par_jour = []

    return DashboardStats(
        total_reponses=total, moy_heures_jour=round(float(moy_heures),2),
        region_top=regions[0]["region"] if regions else "N/A",
        plateforme_top=plateformes[0].plateforme if plateformes else "N/A",
        plateformes=plateformes, regions=regions, tranches_age=tranches_age,
        genres=genres, motivations=motivations,
        bien_etre_moyen=round(float(bien_etre_moyen),2) if bien_etre_moyen else None,
        reponses_par_jour=reponses_par_jour,
    )

@app.get("/analytics/plateformes", response_model=List[StatPlateforme], tags=["Analytics"])
def stats_plateformes(db: Session = Depends(get_db), _: Utilisateur = Depends(get_current_user)):
    total = db.query(func.count(Reponse.id)).scalar() or 0
    plat_fields = {"WhatsApp": Reponse.utilise_whatsapp, "Facebook": Reponse.utilise_facebook,
        "TikTok": Reponse.utilise_tiktok, "Instagram": Reponse.utilise_instagram,
        "YouTube": Reponse.utilise_youtube, "LinkedIn": Reponse.utilise_linkedin,
        "Messenger": Reponse.utilise_messenger, "X (Twitter)": Reponse.utilise_twitter, "Snapchat": Reponse.utilise_snapchat}
    return sorted([StatPlateforme(plateforme=n, count=(db.query(func.count(Reponse.id)).filter(f==True).scalar() or 0),
        pourcentage=_pct(db.query(func.count(Reponse.id)).filter(f==True).scalar() or 0, total))
        for n, f in plat_fields.items()], key=lambda x: x.count, reverse=True)

# ─── ROUTES : IMPORT/EXPORT ──────────────────────────────────────────────────

COLONNES = ["region","ville","tranche_age","genre","niveau_etude","situation_pro",
    "utilise_whatsapp","utilise_facebook","utilise_tiktok","utilise_instagram","utilise_youtube",
    "utilise_linkedin","utilise_messenger","utilise_twitter","utilise_snapchat","autres_plateformes",
    "plateforme_principale","heures_par_jour","motivation_principale","achat_en_ligne","partage_contenu",
    "suivi_actualites","usage_professionnel","impact_bien_etre","commentaire_libre"]

BOOL_COLS = ["utilise_whatsapp","utilise_facebook","utilise_tiktok","utilise_instagram","utilise_youtube",
    "utilise_linkedin","utilise_messenger","utilise_twitter","utilise_snapchat",
    "achat_en_ligne","partage_contenu","suivi_actualites","usage_professionnel"]

def _parse_bool(val):
    if isinstance(val, bool): return val
    return str(val).strip().lower() in ("1","true","oui","yes","vrai")

@app.get("/import-export/template/csv", tags=["Import/Export"])
def telecharger_template():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(COLONNES)
    writer.writerow(["Centre","Yaoundé","18-24","Homme","Supérieur","Étudiant","1","1","0","0","1","0","1","0","0","","WhatsApp","3.5","Communication","0","1","1","0","4","Très utile"])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=template_yegassi.csv"})

@app.get("/import-export/export/csv", tags=["Import/Export"])
def exporter_csv(db: Session = Depends(get_db), _: Utilisateur = Depends(get_admin_user)):
    reponses = db.query(Reponse).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(COLONNES + ["id","source","created_at"])
    for r in reponses:
        writer.writerow([r.region.value if hasattr(r.region,"value") else r.region, r.ville or "",
            r.tranche_age.value if hasattr(r.tranche_age,"value") else r.tranche_age,
            r.genre.value if hasattr(r.genre,"value") else r.genre,
            r.niveau_etude.value if hasattr(r.niveau_etude,"value") else r.niveau_etude,
            r.situation_pro or "", int(r.utilise_whatsapp), int(r.utilise_facebook), int(r.utilise_tiktok),
            int(r.utilise_instagram), int(r.utilise_youtube), int(r.utilise_linkedin),
            int(r.utilise_messenger), int(r.utilise_twitter), int(r.utilise_snapchat),
            r.autres_plateformes or "", r.plateforme_principale or "", r.heures_par_jour,
            r.motivation_principale.value if hasattr(r.motivation_principale,"value") else r.motivation_principale,
            int(r.achat_en_ligne), int(r.partage_contenu), int(r.suivi_actualites), int(r.usage_professionnel),
            r.impact_bien_etre or "", r.commentaire_libre or "", r.id, r.source, str(r.created_at)])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=yegassi_export.csv"})
