FROM registry.cn-hangzhou.aliyuncs.com/miliao/admin:base
COPY ["*.py", "/opt/"]
COPY ["html", "/opt/html/"]
COPY ["templates", "/opt/templates/"]
EXPOSE 80
CMD python3 /opt/admin.py