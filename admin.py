# -*-encoding:utf-8-*-
# http

import json, os, redis, requests, inspect
from functools import wraps
from flask import Flask
from flask import request, send_from_directory, session,render_template,redirect
# from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import *
# 数据库
from sqlalchemy.orm import *
import tool, aes
from tool import *
from setting import *
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta

Base = declarative_base()


#管理员
class Admin(Base):
    __tablename__ = 'admin'
    id = Column(BigInteger, primary_key=True)
    name = Column(String(50), nullable=False, comment="名称")
    pwd = Column(String(32), nullable=False, comment="密码")
    remark = Column(String(200), nullable=True, comment="备注")
    status = Column(Integer, nullable=False, comment="状态(0=正常,1=已封禁)")
    createTime = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


#权限
class Role(Base):
    __tablename__ = 'role'
    id = Column(BigInteger, primary_key=True)
    path = Column(String(200), nullable=False, comment="路径")
    method = Column(String(10), nullable=False, comment="方法")
    name = Column(String(20), nullable=False, comment="名称")
    partten = Column(BigInteger, nullable=True, comment="上级")
    createTime = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


#权限分组
class RoleGroup(Base):
    __tablename__ = 'role_group'
    id = Column(BigInteger, primary_key=True)
    name = Column(String(20), nullable=False, comment="名称")
    roles = Column(String(4096), nullable=False, comment="权限")
    createTime = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


#权限分组-员工关联关系
class AdminRoleGroup(Base):
    __tablename__ = 'rel_admin_role_group'
    id = Column(BigInteger, primary_key=True)
    uid = Column(BigInteger, nullable=False, comment="管理员")
    roleGroup = Column(BigInteger, nullable=False, comment="权限分组")
    createTime = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))



#数据库连接
engine = create_engine(dbUrl, echo=True, pool_pre_ping=True, pool_recycle=300)
engine.execute("select 1").scalar()
#创建表
Base.metadata.create_all(engine)
#读取设置


def get_session(): return sessionmaker(bind=engine, autocommit=True)()


class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if
                          not x.startswith('_') and x != 'metadata' and x != 'password' and x != 'pwd']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data)
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields
        return json.JSONEncoder.default(self, obj)


#接口
app = Flask(__name__)
app.secret_key =secretKey


def login(target_function):
    @wraps(target_function)
    def wrapper(*args, **kwargs):
        if 'sid' in session:
            return target_function(*args, **kwargs)
        else:
            return str("""{"code":401,"msg":"请登陆"}"""), 401

    return wrapper


@app.route('/', methods=['GET'])
def index():
    s = get_session()
    if (len(s.query(Admin).all()) == 0):
        return redirect("/init.html")
    else:
        return redirect("/index.html")



@app.route('/api/admin/init', methods=['POST'])
def init():
    ##页面初始化
    password,group =request.form['password'],request.form['group']
    enpwd = aes.encrypt_token(password)
    s = get_session()
    if(len(s.query(Admin).all())==0):
        ad=Admin(name="admin",pwd=enpwd,remark="自动初始化管理员",status=0)
        rg=RoleGroup(name=group,roles="*")
        s.add(ad)
        s.add(rg)
        s.flush()
        s.refresh(ad)
        s.refresh(rg)
        s.add(AdminRoleGroup(uid=ad.id,roleGroup=rg.id))
        s.flush()
        generateTableRoles
        return json.dumps({"code": 200, "msg": "操作成功"})
    else:
        return str("""{"code":400,"msg":"已经有其他管理员"}"""), 400


@app.route('/api/admin/login', methods=['GET'])
def loginWithPwd():
    name, password = request.args["name"], request.args['password']
    enpwd = aes.encrypt_token(password)
    s = get_session()
    if(len(s.query(Admin).all())==0):
        ad=Admin(name=name,pwd=enpwd,remark="自动初始化管理员",status=0)
        s.add(ad)
        s.flush()
        s.refresh(ad)
        session["sid"] = ad.id
        return json.dumps({"code": 200, "msg": "操作成功", "bean": ad},
                          cls=AlchemyEncoder)
    u = s.query(Admin).filter("name='%s' and pwd='%s'" % (name, enpwd)).all()
    if len(u) == 0: return str("""{"code":400,"msg":"账号或者密码不正确"}"""), 400
    if u[0].status == 1:
        return str("""{"code":400,"msg":"管理员已经被封禁"}"""), 400
    else:
        session["sid"] = u[0].id
        return json.dumps({"code": 200, "msg": "操作成功", "bean": u[0]},
                          cls=AlchemyEncoder)


@app.route('/api/admin/logout', methods=['GET'])
def logout():
    session.clear()
    return json.dumps({"code": 200, "msg": "操作成功"})

row2dict = lambda r: {c.name: str(getattr(r, c.name)) for c in r.__table__.columns}



####菜单生成
@app.route('/json/menu.json', methods=['GET'])
@login
def getMenu():
    s = get_session()
    tables = s.execute("select table_name,table_comment from information_schema.tables  where table_schema = '{}'".format(dbName))
    #处理表注释
    tableInfos={}
    for v in tables:
        d = dict(v.items())
        t,c=d["table_name"],d["table_comment"]
        if c is not None and c!="":
            d=json.loads(c)
            if "ignore" not in d or d["ignore"]==False or d["ignore"]=="false":
                tableInfos[t] = d
    print(tableInfos)
    #处理分组
    partten={}
    for k,v in tableInfos.items():
        if v["partten"] not in partten:
            partten[v["partten"]]=[]
        v["table_name"]=k
        partten[v["partten"]].append(v)
    print(partten)
    #过滤权限
    uid=session["sid"]
    roles=getRedisRoles(uid)
    if "*" not in roles:
        ids=""
        for i in roles:
            if len(ids)>0:
                ids+=","
            ids+=i
        dbRoles = s.execute("select path from role  where id  in ("+ids+") and method='get'")
        roleTables = []
        for v in dbRoles:
            roleTables.append(v["path"])
    #构建菜单
    returnData=[{"id": "console", "title": "控制台", "url": "page/dashboard.html", "icon": "fa fa-dashboard", "open": "true",
          "label": {"text": "NEW", "style": "label-danger"} }]
    if "*" in roles:
        returnData[0]["children"]=[{"id": "table","title": "修改后台","url": "admin/table.html"}]
    id=1
    for k,v in partten.items():
        p={"id": id, "title": k, "children": []}
        id+=1
        for l in v:
            if  "*" in roles or l["table_name"] in roleTables  :
                p["children"].append({"id": id,"title": l["name"],"url": "admin/"+l["table_name"]+".html"})
                id += 1
        if len(p["children"])>0:
            returnData.append(p)
    return json.dumps(returnData)


####列表页面生成
@app.route('/admin/<table>.html', methods=['get'])
def getTableListHtml(table):
    if(os.path.exists("admin_html/"+table+"_list.html")):
        return send_from_directory('admin_html', table+"_list.html")
    s = get_session()
    #查询字段
    names = s.execute("select  column_name, column_comment from information_schema.columns where table_schema ='{}'  and table_name = '{}'".format(dbName,table) )
    #查询表信息
    tables=s.execute("select table_comment from information_schema.tables  where table_schema = '{}' and table_name ='{}'".format(dbName,table)).fetchone()[0]
    tableNames = {}
    tableInfo=json.loads(tables)
    for v in names:
        d = dict(v.items())
        n,c=d["column_name"],d["column_comment"]
        if c is None or c=="":c=n
        if "(" in c:
            c=c[:c.index("(")]
        if "hidden" in tableInfo and n not in tableInfo["hidden"]:
            tableNames[n]=c
    tableInfo["tableNames"]=tableNames
    tableInfo["table"] = table
    print("1")
    return render_template("table.html",**tableInfo)

####新增页面生成
@app.route('/admin/add/<table>.html', methods=['get'])
def getTableAddHtml(table):
    if (os.path.exists("admin_html/" + table + "_add.html")):
        return send_from_directory('admin_html', table + "_add.html")
    s = get_session()
    #查询字段
    names = s.execute("select  character_maximum_length,numeric_precision,is_nullable,column_name, column_comment from information_schema.columns where table_schema ='{}'  and table_name = '{}'".format(dbName,table) )
    #查询表信息
    tables=s.execute("select table_comment from information_schema.tables  where table_schema = '{}' and table_name ='{}'".format(dbName,table)).fetchone()[0]
    tableColInfos = {}
    tableInfo=json.loads(tables)
    for v in names:
        d = dict(v.items())
        n,c=d["column_name"],d["column_comment"]
        if c is None or c=="":c=n
        collen=d["character_maximum_length"]
        if collen is None:
            collen =d["numeric_precision"]
            if collen is None:collen=10
        d["length"]=collen
        if "addIgnore" not in tableInfo or n not in tableInfo["addIgnore"]:
            d["column_comment"]=c
            tableColInfos[n]=d
    tableInfo["tableCols"]=tableColInfos
    tableInfo["table"] = table
    print("1")
    return render_template("table-add.html",**tableInfo)

####编辑页面生成
@app.route('/admin/edit/<table>.html', methods=['get'])
def getTableEditHtml(table):
    if(os.path.exists("admin_html/"+table+"_edit.html")):
        return send_from_directory('admin_html', table+"_edit.html")
    s = get_session()
    #查询字段
    names = s.execute("select  character_maximum_length,numeric_precision,is_nullable,column_name, column_comment from information_schema.columns where table_schema ='{}'  and table_name = '{}'".format(dbName,table) )
    #查询表信息
    tables=s.execute("select table_comment from information_schema.tables  where table_schema = '{}' and table_name ='{}'".format(dbName,table)).fetchone()[0]
    tableColInfos = {}
    tableInfo=json.loads(tables)
    for v in names:
        d = dict(v.items())
        n,c=d["column_name"],d["column_comment"]
        if c is None or c=="":c=n
        collen=d["character_maximum_length"]
        if collen is None:
            collen =d["numeric_precision"]
            if collen is None:collen=10
        d["length"]=collen
        if "addIgnore" not in tableInfo or n not in tableInfo["addIgnore"]:
            d["column_comment"]=c
            tableColInfos[n]=d
    tableInfo["tableCols"]=tableColInfos
    tableInfo["table"] = table
    print("1")
    return render_template("table-edit.html",**tableInfo)




###用户权限分配单独处理

def redisRoleCheck(uid,table,method):
    #检查是否有表的操作权限
    cacheValue=getCache("role_path_"+str(uid))
    if not cacheValue:
        cacheValue=getUserRolePaths(uid)
        putCache("role_path_"+str(uid),cacheValue)
    return (table+method) in cacheValue or "*" in cacheValue

def getUserRolePaths(uid):
    # 获取用户的所有操作权限
    s = engine.connect()
    roles = getRedisRoles(uid)
    if "*" not in roles:
        ids = ""
        for i in roles:
            if len(ids) > 0:
                ids += ","
            ids += i
        dbRoles = s.execute("select path,method from role  where id  in (" + ids + ")")
        roleTables = []
        for v in dbRoles:
            roleTables.append(v["path"]+v["method"])
        return roleTables
    else:
        return ["*"]


def getRedisRoles(uid):
    cacheValue = getCache("role_" + str(uid))
    if not cacheValue:
        cacheValue=getUserRoles(uid)
        putCache("role_" + str(uid), cacheValue)
    return cacheValue



def getUserRoles(uid):
    s=engine.connect()
    srg = s.execute(text("select g.roles from role_group g,rel_admin_role_group rs where rs.roleGroup=g.id and rs.uid=:uid"), uid=uid)
    roles=[]
    for v in srg:
        for l in v["roles"].split(","):
            roles.append(l)
    if "*" in roles:
        return ["*"]
    else:
        return roles




############## 表处理




####表列表
@app.route('/api/admin/table', methods=['GET'])
@login
def getTable():
    s = get_session()
    uid = session["sid"]
    roles = getRedisRoles(uid)
    if "*" not in roles:
        return str("""{"code":403,"msg":"仅限超级管理员操作"}"""), 403
    tables = s.execute("select table_name,table_comment from information_schema.tables  where table_schema = '{}'".format(dbName))
    #处理表注释
    tableInfos=[]
    for v in tables:
        d = dict(v.items())
        t,c=d["table_name"],d["table_comment"]
        names = s.execute(
            "select  character_maximum_length,numeric_precision,is_nullable,column_name, column_comment from information_schema.columns where table_schema ='{}'  and table_name = '{}'".format(
                dbName, t))
        nameList=[]
        for nv in names:
            nameList.append(nv["column_name"])
        if c is not None and c!="":
            c=json.loads(c)
            for i in ["likeKey", "searchKey", "hidden", "action", "limit", "addIgnore", "encrypt"]:
                if (i in c  and len(c[i]) > 0):
                    c[i] = ",".join(c[i])
                else:
                    c[i] = ""
        else:
            c={"name":"","likeKey":"","searchKey":[],"hidden":[],"action":[],"limit":[],"pageSize":100,"partten":"","addIgnore":[],"encrypt":[],"ignore":True}
        c["id"]=t
        c["children"] = nameList
        tableInfos.append(c)
    return json.dumps({"code": 200, "msg": "操作成功", "list": tableInfos, "pageInfo": {"page": 1, "total": len(tableInfos),"pageSize":1000}})






@app.route('/api/admin/table', methods=['put'])
@login
def updateTable():
    # 表注释添加
    #过滤权限
    uid = session["sid"]
    roles = getRedisRoles(uid)
    if "*" not in roles:
        return str("""{"code":403,"msg":"仅限超级管理员操作"}"""), 403
    # 取出参数
    params = request.form.to_dict()
    # 构造查询条件
    for i in ["likeKey","searchKey","hidden","action","limit","addIgnore","encrypt"]:
        if(i in params and len(params[i])>0):
            params[i]=list(params[i].split(","))
        else:
            params[i]=[]
    print(params)
    params["ignore"]=params["ignore"]=="true"
    tableName=params.pop("id")
    s = engine.connect()
    id=s.execute(f"ALTER TABLE {tableName} COMMENT='{json.dumps(params,ensure_ascii=False)}'").rowcount
    return json.dumps({"code": 200, "msg": "修改成功"})






#####################权限





@app.route('/api/admin/rel_admin_role_group', methods=['put',"post"])
@login
def updateStaffRoleGroups():
    # 权限更新
    #过滤权限
    if not redisRoleCheck(session["sid"],"rel_admin_role_group","POST") and not redisRoleCheck(session["sid"],"rel_admin_role_group","PUT"):
        return str("""{"code":403,"msg":"无权操作,请联系管理员授权"}"""), 403
    s = engine.connect()
    uid,roleGroup=request.form["uid"],set(request.form["roleGroup"].split(","))
    if len(roleGroup)==0 or (list(roleGroup)[0]=='' and len(roleGroup)==1):
       count= s.execute(text("delete from rel_admin_role_group where uid=:uid"), uid=uid).rowcount
       return json.dumps({"code": 200, "msg": "成功删除"+str(count)+"条数据"})
    srg = s.execute(text("select id,roleGroup from rel_admin_role_group where uid=:uid"),uid=uid)
    dbIds=set()
    addCount=0
    delCount=0
    for v in srg:
        dbIds.add(v["roleGroup"])
        if int(v["roleGroup"]) not in roleGroup:
            s.execute(text("delete from rel_admin_role_group where id=:id"), id=v["id"])
            delCount+=1
    for v in roleGroup:
        if v not in dbIds:
            s.execute(text("INSERT INTO rel_admin_role_group (uid,roleGroup) VALUES (:uid,:roleGroup)"),uid=uid,roleGroup=v)
            addCount+=1
    #更新用户权限到redis
    putCache("role_"+uid,getUserRoles(uid))
    putCache("role_path_" + uid, getUserRolePaths(uid))
    return json.dumps({"code": 200, "msg": "添加成功"+str(addCount)+"条数据,删除"+str(delCount)+"条数据"})



@app.route('/api/admin/rel_admin_role_group', methods=['get'])
@login
def getRelStaffRoleGroups():
    # 员工权限查询
    #查出所有已经分配了权限的用户
    #显示  名称  手机号码  权限组   分页
    #过滤权限
    if not redisRoleCheck(session["sid"],"rel_admin_role_group","GET"):
        return str("""{"code":403,"msg":"无权操作,请联系管理员授权"}"""), 403
    # 取出分页
    params = request.args.to_dict()
    page,pageSize = int(params.pop("page", "1")),int(params.pop("pageSize", "10"))
    nameLike=params.pop("like","")
    s = engine.connect()
    sta = s.execute("select * from admin")
    admins={}
    #查询所有员工
    for v in sta:
        d = dict(v.items())
        admins[d["id"]]=d
    rgro = s.execute("select * from role_group")
    groups = {}
    #查询所有权限
    for v in rgro:
        d = dict(v.items())
        groups[d["id"]] = d

    srg = s.execute("select * from rel_admin_role_group")
    adminGroupIds={}
    adminIds=set()
    for v in srg:
        d = dict(v.items())
        uid,gid=d["uid"],d["roleGroup"]
        if uid not in adminGroupIds:
            adminGroupIds[uid]=[]
        adminGroupIds[uid].append(gid)
        if nameLike is not None and len(nameLike)>0:
            if nameLike in admins[uid]["realName"]:
                adminIds.add(uid)
        else:
            adminIds.add(uid)
    start=(page-1)*pageSize
    pageIds=[]
    adminIds=list(adminIds)
    adminIds.sort()
    if start < len(adminIds):
        if (start+pageSize)<=len(adminIds):
            pageIds=adminIds[start:start+pageSize]
        else:
            pageIds = adminIds[start:]
    adminDatas=[]
    for v in pageIds:
        admin=admins[v]
        groupIds=adminGroupIds[v]
        groupNames=""
        groupIdStr=""
        for g in groupIds:
            if len(groupNames)>0:
                groupNames+=","
            groupNames+=groups[g]["name"]
            if len(groupIdStr)>0:
                groupIdStr+=","
            groupIdStr+=str(g)
        adminDatas.append({"uid":v,"name":admin["name"],"remark":admin["remark"],"groupName":groupNames,"roleGroup":groupIdStr})

    return json.dumps({"code": 200, "msg": "操作成功", "list": adminDatas, "pageInfo": {"page": page, "total": len(adminIds),"pageSize":pageSize}})




@app.route('/api/admin/generateRole', methods=['PUT'])
def generateTableRoles():
    # 生成权限
    s = engine.connect()
    dbTableNames = s.execute("select table_name,table_comment from information_schema.tables  where table_schema = '{}'".format(dbName))
    #处理表注释
    tableNames={}
    for v in dbTableNames:
        d = dict(v.items())
        t,c=d["table_name"],d["table_comment"]
        if c is not None and c!="":
            d=json.loads(c)
            tableNames[t]=d["name"]
    dbTables = s.execute("show tables")
    dbRoles= s.execute("select id,path,method from role")
    allRoles={}
    count=0
    for l in dbRoles:
        allRoles[l["path"]+","+l["method"]]=l["id"]
    for t in dbTables:
        tableName=t[0]
        if tableName in tableNames:
            #遍历表，检查是否有对应的权限,同时创建对应的权限
            if tableName+",GET" not in allRoles:
                id=s.execute("INSERT INTO role (`path`, `method`, `name`, `partten`) VALUES ('"+tableName+"','GET', '"+tableNames[tableName]+"列表', NULL)").lastrowid
                count+=1
            else:
                id=allRoles[tableName+",GET"]
            id=str(id)
            if tableName + ",POST" not in allRoles:
                s.execute("INSERT INTO role (`path`, `method`, `name`, `partten`) VALUES ('" + tableName + "','POST', '" +tableNames[tableName] + "创建', "+id+")")
                count += 1
            if tableName + ",DELETE" not in allRoles:
                s.execute("INSERT INTO role (`path`, `method`, `name`, `partten`) VALUES ('" + tableName + "','DELETE', '" +tableNames[tableName] + "删除', "+id+")")
                count += 1
            if tableName + ",PUT" not in allRoles:
                s.execute("INSERT INTO role (`path`, `method`, `name`, `partten`) VALUES ('" + tableName + "','PUT', '" +tableNames[tableName] + "修改', "+id+")")
                count += 1
    return json.dumps({"code": 200, "msg": "操作成功"+str(count)+"条"})





##############通用接口





@app.route('/api/admin/<table>', methods=['post'])
@login
def addTables(table):
    # 通用表添加
    #过滤权限
    if not redisRoleCheck(session["sid"],table,"POST"):
        return str("""{"code":403,"msg":"无权操作,请联系管理员授权"}"""), 403
    s = engine.connect()
    tables=s.execute("select table_comment from information_schema.tables  where table_schema = '{}' and table_name ='{}'".format(dbName,table)).fetchone()[0]
    tableInfo=json.loads(tables)
    # 取出参数
    params = request.form.to_dict()
    # 构造查询条件
    addKey=""
    addValue=""
    if len(params) > 0:
        for k, v in params.items():
            if len(v) > 0 and k != "_":
                if "encrypt" in tableInfo and k in tableInfo["encrypt"]:
                    v=aes.encrypt_token(v)
                    params[k] = v
                if len(addKey)>0:
                    addKey+=","+k
                    addValue += ",:"+k+""
                else:
                    addKey += k
                    addValue += ":"+k+""
    #查询数据总数

    id = s.execute(text("INSERT INTO `"+table+"` ("+addKey+") VALUES ("+addValue+")"),**params).rowcount
    # 查询数据
    return json.dumps({"code": 200, "msg": "插入成功"+str(id)+"条数据"})




@app.route('/api/admin/<table>', methods=['delete'])
@login
def deleteTables(table):
    # 通用表添加
    #过滤权限
    if not redisRoleCheck(session["sid"],table,"DELETE"):
        return str("""{"code":403,"msg":"无权操作,请联系管理员授权"}"""), 403
    s = engine.connect()
    # 取出参数
    idlist= request.args["ids"]
    ids = ""
    for i in idlist.split(","):
        if len(ids) > 0:
            ids += ","
        ids += i
    count = s.execute("delete from `"+table+"`  where id  in (" + ids + ")").rowcount
    # 查询数据
    return json.dumps({"code": 200, "msg": "删除成功"+str(count)+"条数据"})



@app.route('/api/admin/<table>/<id>', methods=['put'])
@login
def updateTables(table,id):
    # 通用表更新
    #过滤权限
    if not redisRoleCheck(session["sid"],table,"PUT"):
        return str("""{"code":403,"msg":"无权操作,请联系管理员授权"}"""), 403
    s = engine.connect()
    tables=s.execute("select table_comment from information_schema.tables  where table_schema = '{}' and table_name ='{}'".format(dbName,table)).fetchone()[0]
    tableInfo=json.loads(tables)
    # 取出参数
    params = request.form.to_dict()
    # 构造更新条件
    update=""
    if len(params) > 0:
        for k, v in params.items():
            if len(v) > 0 and k != "_":
                if "encrypt" in tableInfo and k in tableInfo["encrypt"]:
                    v=aes.encrypt_token(v)
                    params[k]=v
                if len(update)>0:
                    update += ","+ k+"=:"+k
                else:
                    update += k+"=:"+k
    #查询数据总数
    count = s.execute(text("UPDATE `"+table+"`  SET "+update+"  where id='"+id+"'"),**params).rowcount
    # 查询数据
    return json.dumps({"code": 200, "msg": "更新成功"+str(count)+"条数据"})

@app.route('/api/admin/<table>', methods=['get'])
@login
def getTables(table):
    # 通用表查询
    #过滤权限
    if not redisRoleCheck(session["sid"],table,"GET"):
        return str("""{"code":403,"msg":"无权操作,请联系管理员授权"}"""), 403
    s = engine.connect()
    # 取出参数
    params = request.args.to_dict()
    # 取出分页
    page,pageSize = params.pop("page", "1"),params.pop("pageSize", "10")
    # 取出模糊查询条件
    like,likeName = params.pop("like", ""),params.pop("likeName", "")
    # 构造查询条件
    where = ""
    if len(params) > 0:
        for k, v in params.items():
            if len(v) > 0 and k != "_":
                if len(where) > 0: where += " and "
                where += " " + k + " ='" + v + "'"
    if len(like) > 0 and len(likeName) > 0:
        if len(where) > 0: where += " and "
        where += " " + likeName + " like '%%" + like + "%%'"
    if len(where) > 0: where = " where " + where
    #查询数据总数
    total = s.execute("select count(*) from " + table + where).fetchone()[0]
    # 查询数据
    where += " limit " + str((int(page) - 1) * int(pageSize)) + "," + pageSize
    q = s.execute("select * from " + table + where)
    #清理数据
    datas = []
    for v in q:
        d = dict(v.items())
        if "createTime" in d:
            d["createTime"] = d["createTime"].strftime('%Y-%m-%d %H:%M:%S')
        datas.append(d)
    return json.dumps({"code": 200, "msg": "操作成功", "list": datas, "pageInfo": {"page": page, "total": total,"pageSize":pageSize}})




################# 静态资源


@app.route('/<path:path>')
def send_static(path):
    return send_from_directory('html', path)

# http系统入口
app.run(host='0.0.0.0', port=80, debug=debug)
