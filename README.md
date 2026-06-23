# Ansible DEMO #
Ansible demo to copy files to s3 bucket in aws

Welcome to the **DevSecOps** Udemy Tutorial repository!  
This repository contains resources and links to our Udemy courses, focusing on **DevSecOps** (a blend of DevOps + Security). Whether you're a **Freshers**, **DevOps Engineer**, **Application Support Specialist**, **QA Professional**, or in **Infosec**, these courses are designed for professionals at all levels.

## Course Overview:
We provide **professional-level training** in DevSecOps, covering tools and practices used in the industry to secure your applications and infrastructure while embracing DevOps practices.

## architecture ##

```text
Start
  │
  ▼
Is AI_PROVIDER set?
  │
  ├── Yes
  │     │
  │     ▼
  │  Return AI_PROVIDER value
  │
  └── No
        │
        ▼
Is OPENAI_API_KEY or AI_API_KEY set?
        │
        ├── Yes
        │     ▼
        │  Use OpenAI-compatible provider
        │
        └── No
              │
              ▼
Are OPENAI_BASE_URL and AI_MODEL set?
              │
              ├── Yes
              │     ▼
              │  Use OpenAI-compatible provider
              │
              └── No
                    ▼
                 Use Ollama

 Jenkins AI Failure Analysis Flow 

Jenkins Build Failure
        │
        ▼
Collect Last 250 Log Lines
        │
        ▼
Limit to 12,000 Characters
        │
        ▼
Write failure-log.txt
        │
        ▼
Execute jenkins_ai_summary.py
        │
        ▼
Resolve AI Provider
        │
        ├── OpenAI
        ├── Azure OpenAI
        ├── OpenAI-Compatible APIs
        └── Ollama
        │
        ▼
Send Logs to LLM
        │
        ▼
Generate Root Cause Analysis
        │
        ▼
Return Human-Readable Summary
        │
        ▼
Publish to Jenkins / Slack / Email

---
```

## My Udemy Online Courses:

### 🚀 **DevSecOps**
- Learn the essentials of DevSecOps and how security integrates with the DevOps pipeline.  
[**DevSecOps Course**](https://tinyurl.com/2p8dxbwn)

### 🚀 **DevSecOps Fundamentals**
- A foundational course covering the core concepts of DevSecOps for beginners.  
[**DevSecOps Fundamentals**](https://shorturl.at/H9kqG)

### 🚀 **SonarQube**
- Master SonarQube to analyze and improve the quality of your code with automated security checks.  
[**SonarQube Course**](https://tinyurl.com/mzfukn4p)

### 🚀 **Serverless**
- Dive into serverless architectures and build efficient, scalable applications.  
[**Serverless Course**](https://tinyurl.com/st5xde5z)

### 🚀 **Docker**
- Learn Docker, containerization, and Kubernetes to run your apps in any environment effortlessly.  
[**Docker Course**](https://tinyurl.com/2ffv8yjn)

### 🚀 **CI/CD Jenkins Master**
- Master Jenkins and automate your software build and delivery pipeline.  
[**Jenkins Master Course**](https://rb.gy/u0ygq)

### 🚀 **Free Linux Course: Introduction to Linux Crash Course**
- Get started with Linux, the backbone of many modern IT systems.  
[**Linux Crash Course**](https://www.udemy.com/course/introduction-to-linux-crash-course)

### 🚀 **AWS DevOps Certification: DOP-C01 Practice Test**
- Prepare for the AWS DevOps Engineer - Professional exam with this practice test.  
[**AWS DevOps Practice Test**](https://www.udemy.com/course/aws-devops-practice-test/?referralCode=D8209AD57D310A001C78)

### 🚀 **Cloudflare tutorial**
- Cloudflare WAF for DevSecOps, & Cloud Security Engineers  
[**Cloudflare tutorial**](https://www.udemy.com/course/cloudflare/?referralCode=CDCEC8AAAA79BEF5777D)

### 🚀 **Complete GitLab DevOps Bootcamp: CI/CD, Terraform, Ansible**
- Get started with gitlab devops tutorial . 
[**Complete GitLab DevOps Bootcamp: CI/CD, Terraform, Ansible**](https://www.udemy.com/course/complete-gitlab-devops-bootcamp-cicd-terraform-ansible/?referralCode=8C54F936960F5B9F7177)


---

## Course Tags:
**#DevSecOps** | **#DevOps** | **#SonarQube** | **#infosec** | **#security** | **#sast** | **#serverless** | **#cloud** | **#computing** | **#CI/CD** | **#Jenkins** | **#Docker** | **#Linux** | **#containerization** | **#automation** | **#AWS** | **#DevOpsCertification**

---

### 🚀 Reach out for any **discounts** available this month!

Thank you for visiting! Don't forget to check out the courses and **reach out for discounts**!
