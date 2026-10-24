import hashlib
import ipaddress
import random
import socket
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(
    page_title="TrafficSense | Website Insights",
    page_icon="TS",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------- Design ----------

st.markdown(
    """
    <style>
    .stApp {
        background: #f5f8fc;
        color: #172033;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1.8rem;
        padding-bottom: 3rem;
    }

    .topbar {
        padding: 18px 24px;
        background: #ffffff;
        border: 1px solid #e5eaf2;
        border-radius: 14px;
        margin-bottom: 28px;
    }

    .brand {
        color: #2459d3;
        font-size: 25px;
        font-weight: 800;
        margin: 0;
    }

    .subbrand {
        color: #64748b;
        font-size: 14px;
        margin: 4px 0 0 0;
    }

    .eyebrow {
        color: #2459d3;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 1.5px;
    }

    .hero-title {
        font-size: clamp(30px, 4vw, 46px);
        font-weight: 800;
        line-height: 1.15;
        color: #172033;
        margin: 5px 0 12px 0;
    }

    .hero-description {
        font-size: 17px;
        color: #64748b;
        max-width: 760px;
        line-height: 1.7;
    }

    .section-card {
        background: #ffffff;
        padding: 22px;
        border: 1px solid #e5eaf2;
        border-radius: 14px;
        margin: 16px 0;
    }

    .metric-card {
        background: #ffffff;
        border: 1px solid #e5eaf2;
        border-radius: 14px;
        padding: 20px;
        min-height: 125px;
    }

    .metric-label {
        color: #64748b;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 9px;
    }

    .metric-value {
        color: #2459d3;
        font-size: 28px;
        font-weight: 800;
        margin: 0;
    }

    .metric-note {
        color: #64748b;
        font-size: 12px;
        margin-top: 5px;
    }

    .demo-notice {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
        color: #1e40af;
        padding: 14px 16px;
        margin: 18px 0;
        line-height: 1.6;
    }

    .website-info {
        background: #ffffff;
        border: 1px solid #e5eaf2;
        border-radius: 14px;
        padding: 20px;
        margin: 14px 0;
        line-height: 1.8;
        overflow-wrap: anywhere;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        background: #2459d3;
        color: white;
        border: 1px solid #2459d3;
        border-radius: 9px;
        font-weight: 700;
        min-height: 42px;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        background: #1946ad;
        color: white;
        border-color: #1946ad;
    }

    h1, h2, h3 {
        color: #172033;
    }

    @media (max-width: 640px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .topbar {
            padding: 15px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- URL validation ----------

HEADERS = {
    "User-Agent": "TrafficSenseWebsiteInspector/1.0"
}


def validate_url(raw_url):
    raw_url = raw_url.strip()

    if not raw_url:
        raise ValueError("Enter a website address first.")

    if "://" not in raw_url:
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS addresses are supported.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Enter a valid public website address.")

    try:
        port = parsed.port
    except ValueError:
        raise ValueError("The website address contains an invalid port.")

    if port is not None and port not in (80, 443):
        raise ValueError("Custom ports are not supported.")

    host = parsed.hostname.lower().rstrip(".")

    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Local and private websites are not supported.")

    try:
        resolved = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError):
        raise ValueError("The domain could not be found. Check the address.")

    if not resolved:
        raise ValueError("The domain did not resolve to an IP address.")

    for result in resolved:
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError(
                "Only publicly accessible website addresses are supported."
            )

    return raw_url


# ---------- Website inspection ----------

def inspect_website(raw_url):
    safe_url = validate_url(raw_url)

    try:
        response = requests.get(
            safe_url,
            headers=HEADERS,
            timeout=8,
            allow_redirects=False,
            stream=True,
        )
    except requests.RequestException:
        raise ValueError(
            "Could not connect to this website. Check the address and try again."
        )

    try:
        if 300 <= response.status_code < 400:
            raise ValueError(
                "This website redirects to another address. "
                "Try entering its final HTTPS address."
            )

        if response.status_code >= 400:
            raise ValueError(
                f"The website returned HTTP {response.status_code}. "
                "Check the address or try another public webpage."
            )

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type:
            raise ValueError(
                "This address did not return an HTML webpage."
            )

        chunks = []
        total_size = 0

        for chunk in response.iter_content(chunk_size=16384):
            if not chunk:
                continue

            remaining = 1_000_000 - total_size
            if remaining <= 0:
                break

            chunk = chunk[:remaining]
            chunks.append(chunk)
            total_size += len(chunk)

            if total_size >= 1_000_000:
                break

        html = b"".join(chunks).decode(
            response.encoding or "utf-8",
            errors="replace",
        )

        status_code = response.status_code
        final_url = safe_url

    finally:
        response.close()

    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(final_url)

    title_tag = soup.find("title")
    title = (
        title_tag.get_text(" ", strip=True)
        if title_tag
        else "Title not available"
    )

    description_tag = soup.find(
        "meta",
        attrs={"name": "description"},
    )

    description = (
        description_tag.get("content", "").strip()
        if description_tag
        else "Description not available."
    )

    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        link_url = urljoin(final_url, tag["href"])
        link_parsed = urlparse(link_url)

        if link_parsed.scheme not in ("http", "https"):
            continue

        if link_url not in seen:
            seen.add(link_url)
            links.append(
                {
                    "text": tag.get_text(" ", strip=True) or "Unnamed link",
                    "url": link_url,
                }
            )

        if len(links) >= 12:
            break

    return {
        "url": final_url,
        "domain": parsed.netloc,
        "title": title,
        "description": description,
        "status": status_code,
        "links": links,
    }


# ---------- Synthetic demo data ----------

def make_demo_analytics(domain):
    seed = int(hashlib.sha256(domain.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    labels = []
    page_views = []
    unique_visitors = []
    returning_visitors = []
    records = []

    today = date.today()

    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)

        views = rng.randint(450, 1800)
        unique = int(views * rng.uniform(0.55, 0.78))
        returning = int(unique * rng.uniform(0.15, 0.35))

        labels.append(day.strftime("%d %b"))
        page_views.append(views)
        unique_visitors.append(unique)
        returning_visitors.append(returning)

        records.append(
            {
                "Date": day.strftime("%d %b %Y"),
                "Page Views": views,
                "Unique Visitors": unique,
                "Returning Visitors": returning,
            }
        )

    total_views = sum(page_views)
    total_unique = sum(unique_visitors)
    total_returning = sum(returning_visitors)
    average_views = round(total_views / len(page_views))

    recent_average = sum(page_views[-7:]) / 7

    projection = []

    for i in range(1, 8):
        projection.append(
            {
                "Date": (today + timedelta(days=i)).strftime("%d %b"),
                "Example Page Views": max(
                    0,
                    round(recent_average * rng.uniform(0.9, 1.1)),
                ),
            }
        )

    chart_data = pd.DataFrame(
        {
            "Illustrative page views": page_views,
            "Illustrative unique visitors": unique_visitors,
        },
        index=labels,
    )
    chart_data.index.name = "Date"

    return {
        "total_views": total_views,
        "total_unique": total_unique,
        "total_returning": total_returning,
        "average_views": average_views,
        "records": records,
        "projection": projection,
        "chart_data": chart_data,
    }


# ---------- Page layout ----------

st.markdown(
    """
    <div class="topbar">
        <p class="brand">TrafficSense</p>
        <p class="subbrand">Website Traffic Insights</p>
    </div>
    <p class="eyebrow">WEBSITE ANALYTICS PROJECT</p>
    <p class="hero-title">Understand your website</p>
    <p class="hero-description">
        Inspect public website information and explore a traffic dashboard
        with sample records, charts and illustrative projections.
    </p>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("Inspect a website")
st.write("Enter a publicly accessible website address to get started.")

with st.form("website_inspection_form", clear_on_submit=False):
    website_url = st.text_input(
        "Website URL",
        placeholder="https://example.com",
        key="website_url_input",
    )

    submitted = st.form_submit_button(
        "Inspect Website",
        use_container_width=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="demo-notice">
        <strong>Demo data:</strong> Traffic figures, visitor records and
        projections are synthetic examples. TrafficSense does not access
        private website analytics and does not measure actual visitor counts.
    </div>
    """,
    unsafe_allow_html=True,
)

if "website_result" not in st.session_state:
    st.session_state.website_result = None

if "inspection_error" not in st.session_state:
    st.session_state.inspection_error = None

if submitted:
    st.session_state.website_result = None
    st.session_state.inspection_error = None

    try:
        with st.spinner("Inspecting the public webpage..."):
            website = inspect_website(website_url)
            analytics = make_demo_analytics(website["domain"])

        st.session_state.website_result = {
            "website": website,
            "analytics": analytics,
        }

    except ValueError as exc:
        st.session_state.inspection_error = str(exc)

    except Exception:
        st.session_state.inspection_error = (
            "An unexpected error occurred. Please try another public website."
        )

if st.button("Reset results", use_container_width=False):
    st.session_state.website_result = None
    st.session_state.inspection_error = None
    st.session_state.website_url_input = ""
    st.rerun()

if st.session_state.inspection_error:
    st.error(st.session_state.inspection_error)

if st.session_state.website_result:
    result = st.session_state.website_result
    website = result["website"]
    analytics = result["analytics"]

    st.divider()

    heading_col, status_col = st.columns([4, 1])

    with heading_col:
        st.markdown(
            '<p class="eyebrow">WEBSITE OVERVIEW</p>',
            unsafe_allow_html=True,
        )
        st.header(website["title"])
        st.caption(website["domain"])

    with status_col:
        st.metric("HTTP Status", website["status"])

    st.markdown('<div class="website-info">', unsafe_allow_html=True)
    st.subheader("Public website information")
    st.write(website["description"])
    st.write("**Website address:**", website["url"])
    st.write("**Public links found:**", len(website["links"]))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="demo-notice">
            <strong>Illustrative statistics only:</strong>
            The following visitor numbers are generated sample data,
            not actual measured traffic.
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)

    metrics = [
        ("Simulated Page Views", analytics["total_views"]),
        ("Simulated Unique Visitors", analytics["total_unique"]),
        ("Returning Visitors", analytics["total_returning"]),
        ("Average Daily Page Views", analytics["average_views"]),
    ]

    for column, (label, value) in zip(metric_cols, metrics):
        with column:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <p class="metric-value">{value:,}</p>
                    <div class="metric-note">Synthetic demo data</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.subheader("Illustrative traffic trend")
    st.caption("Example page views and unique visitors across 14 days.")
    st.line_chart(analytics["chart_data"], use_container_width=True)

    st.subheader("Illustrative visitor records")
    st.caption(
        "These records are generated for demonstration and were not "
        "collected from the inspected website."
    )
    st.dataframe(
        pd.DataFrame(analytics["records"]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Illustrative 7-day projection")
    st.caption(
        "A simple projection based on synthetic sample data; "
        "it is not a reliable forecast of actual traffic."
    )

    projection_cols = st.columns(4)

    for i, item in enumerate(analytics["projection"]):
        with projection_cols[i % 4]:
            st.metric(
                label=item["Date"],
                value=f'{item["Example Page Views"]:,}',
            )

    st.subheader("Public links found on the page")

    if website["links"]:
        for link in website["links"]:
            st.markdown(
                f'[{link["text"]}]({link["url"]})',
                help=link["url"],
            )
            st.caption(link["url"])
    else:
        st.info("No public links were found in the webpage HTML.")

st.divider()
st.caption(
    "TrafficSense is an educational demonstration. "
    "Synthetic statistics are not actual website analytics."
)
