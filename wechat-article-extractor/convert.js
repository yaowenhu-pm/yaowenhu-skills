#!/usr/bin/env node
// 微信公众号文章 → Markdown 转换 CLI
//
// 用法：
//   node convert.js <mp.weixin.qq.com 文章URL> [输出.md]
//   node convert.js <extract结果.json> [输出.md]
//
// 输出带 frontmatter（标题/作者/时间/原文链接）的 Markdown 文件，
// 默认保存为当前目录下 <文章标题>.md。

const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { extract } = require('./scripts/extract.js');

function htmlToMarkdown(data) {
  const $ = cheerio.load(data.msg_content || '', { decodeEntities: false });

  let markdown = `---
title: "${data.msg_title}"
author: "${data.msg_author || data.account_name}"
date: "${data.msg_publish_time_str}"
source: "${data.account_name}"
original_url: "${data.msg_link}"
---

# ${data.msg_title}

**作者**: ${data.msg_author || data.account_name}
**发布时间**: ${data.msg_publish_time_str}
**公众号**: ${data.account_name}
**原文链接**: ${data.msg_link}

---

`;

  function processElement(elem) {
    const $elem = $(elem);
    const tagName = elem.tagName?.toLowerCase();

    if (!tagName) return;

    if (tagName === 'h1' || tagName === 'h2') {
      markdown += '\n## ' + $elem.text().trim() + '\n\n';
    } else if (tagName === 'h3' || tagName === 'h4') {
      markdown += '\n### ' + $elem.text().trim() + '\n\n';
    } else if (tagName === 'p') {
      let text = '';
      $elem.contents().each((i, child) => {
        if (child.type === 'text') {
          text += child.data;
        } else if (child.type === 'tag') {
          const $child = $(child);
          if (child.tagName === 'strong' || child.tagName === 'b') {
            const childText = $child.text().trim();
            if (childText) text += '**' + childText + '**';
          } else if (child.tagName === 'br') {
            text += '\n';
          } else if (child.tagName === 'img') {
            const src = $child.attr('data-src') || $child.attr('src');
            if (src) text += '\n![图片](' + src + ')\n';
          } else {
            text += $child.text();
          }
        }
      });
      text = text.trim();
      if (text) markdown += text + '\n\n';
    } else if (tagName === 'blockquote') {
      const text = $elem.text().trim();
      if (text) markdown += '> ' + text + '\n\n';
    } else if (tagName === 'ol') {
      $elem.children('li').each((i, li) => {
        const text = $(li).text().trim();
        if (text) markdown += (i + 1) + '. ' + text + '\n';
      });
      markdown += '\n';
    } else if (tagName === 'ul') {
      $elem.children('li').each((i, li) => {
        const text = $(li).text().trim();
        if (text) markdown += '- ' + text + '\n';
      });
      markdown += '\n';
    } else if (tagName === 'img') {
      const src = $elem.attr('data-src') || $elem.attr('src');
      if (src) markdown += '\n![图片](' + src + ')\n\n';
    } else if (tagName === 'code') {
      const text = $elem.text().trim();
      if (text) markdown += '`' + text + '`';
    } else if (tagName === 'pre' || (tagName === 'section' && $elem.hasClass('code-snippet__fix'))) {
      const codeText = $elem.find('code').text() || $elem.text();
      if (codeText.trim()) {
      markdown += '\n```\n' + codeText.trim() + '\n```\n\n';
      }
    } else if (tagName === 'section' || tagName === 'div' || tagName === 'center' || tagName === 'span') {
      $elem.children().each((i, child) => {
        processElement(child);
      });
    }
  }

  $('body').children().each((i, child) => {
    processElement(child);
  });

  return markdown.replace(/\n{3,}/g, '\n\n');
}

async function main() {
  const [input, output] = process.argv.slice(2);
  if (!input) {
    console.error('用法: node convert.js <文章URL或extract结果.json> [输出.md]');
    process.exit(1);
  }

  let data;
  if (/^http/.test(input)) {
    const result = await extract(input);
    if (!result.done) {
      console.error(`提取失败 (code ${result.code}): ${result.msg}`);
      process.exit(1);
    }
    data = result.data;
  } else {
    const parsed = JSON.parse(fs.readFileSync(input, 'utf8'));
    data = parsed.data || parsed; // 兼容整个 extract 返回值或其 data 字段
  }

  const markdown = htmlToMarkdown(data);
  const safeTitle = (data.msg_title || 'article').replace(/[\\/:*?"<>|]/g, '_');
  const outputPath = output || path.join(process.cwd(), safeTitle + '.md');
  fs.writeFileSync(outputPath, markdown, 'utf8');

  console.log('文件已保存到:', outputPath);
  console.log('文件大小:', (markdown.length / 1024).toFixed(2), 'KB');
}

main().catch((e) => {
  console.error('转换失败:', e.message);
  process.exit(1);
});
