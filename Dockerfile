FROM livehl/admin:base
COPY ["*.py", "/opt/"]
COPY ["html", "/opt/html/"]
COPY ["admin_html", "/opt/admin_html/"]
COPY ["templates", "/opt/templates/"]
EXPOSE 80
WORKDIR /opt/
CMD python3 /opt/admin.py