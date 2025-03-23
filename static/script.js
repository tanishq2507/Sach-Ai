document.getElementById('analyze-btn').addEventListener('click', function() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) {
    alert('Please enter a valid URL');
    return;
  }
  // Show loader and hide previous results
  document.getElementById('loader').style.display = 'block';
  document.getElementById('result').style.display = 'none';
  
  fetch('/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url: url }),
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return response.json();
  })
  .then(data => {
    // Check if there's an error message about transcript
    if (data.error && data.error.includes('transcript')) {
      document.getElementById('loader').style.display = 'none';
      alert(data.error);
      return;
    }
    
    // Hide loader and show result
    document.getElementById('loader').style.display = 'none';
    document.getElementById('result').style.display = 'block';
    
    // Update metadata section
    const metadataDiv = document.getElementById('metadata');
    let metadataHTML = '';
    if (data.content_type === 'youtube') {
      metadataHTML = `
        <div class="metadata-item"><span class="metadata-label">Content Type:</span> YouTube Video</div>
        <div class="metadata-item"><span class="metadata-label">Title:</span> ${data.metadata.title || 'Unknown'}</div>
        <div class="metadata-item"><span class="metadata-label">Creator:</span> ${data.metadata.author || 'Unknown'}</div>
      `;
    } else {
      metadataHTML = `
        <div class="metadata-item"><span class="metadata-label">Content Type:</span> Article</div>
        <div class="metadata-item"><span class="metadata-label">Title:</span> ${data.metadata.title || 'Unknown'}</div>
        <div class="metadata-item"><span class="metadata-label">Source:</span> ${data.metadata.source || 'Unknown'}</div>
        <div class="metadata-item"><span class="metadata-label">Published:</span> ${data.metadata.publication_date || 'Unknown'}</div>
      `;
    }
    metadataDiv.innerHTML = metadataHTML;
    
    // Format and display summary and analysis
    document.getElementById('summary-text').innerHTML = formatContent(data.summary, true);
    document.getElementById('analysis-text').innerHTML = formatContent(data.critical_analysis, false);
    
    // Update source link
    const sourceLink = document.getElementById('source-link');
    sourceLink.href = data.source_url;
  })
  .catch(error => {
    document.getElementById('loader').style.display = 'none';
    alert('Error: ' + error.message);
    console.error('Error:', error);
  });
});

// Function to format content and ensure proper link handling
function formatContent(content, isSummary) {
  if (!content) return "";
  
  // Escape HTML characters
  content = content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
  
  // Convert standalone URLs to clickable links
  content = content.replace(
    /(https?:\/\/[^\s"<>]+\.[^\s"<>]+)/g, 
    '<a href="$1" target="_blank" rel="noopener">$1</a>'
  );
  
  // Convert markdown-style links to HTML links
  content = content.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g, 
    function(match, text, url) {
      if (!/^https?:\/\//i.test(url)) {
        url = 'https://' + url;
      }
      return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
    }
  );
  
  // Format fact check blocks
  content = content.replace(
    /\*\*(Claim|CLAIM):\*\*\s*([\s\S]*?)(?=\*\*(Verdict|VERDICT|Rating|RATING):|$)/gi, 
    '<div class="fact-check"><span class="claim">Claim:</span> $2</div>'
  );
  
  // Format verdict/rating indicators
  content = content.replace(
    /\*\*(Verdict|VERDICT|Rating|RATING):\*\*\s*([\s\S]*?)(?=\n\n|\*\*(Claim|CLAIM):|$)/gi, 
    function(match, p1, p2) {
      let className = '';
      const lowerP2 = p2.toLowerCase();
      if (lowerP2.includes('true') || lowerP2.includes('accurate')) {
        className = 'true';
      } else if (lowerP2.includes('false') || lowerP2.includes('inaccurate')) {
        className = 'false';
      } else if (lowerP2.includes('misleading') || lowerP2.includes('partially')) {
        className = 'misleading';
      } else {
        className = 'uncertain';
      }
      return `<div><span class="claim">${p1}:</span> <span class="${className}">${p2.trim()}</span></div>`;
    }
  );
  
  // Convert markdown headings to HTML
  content = content.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
  content = content.replace(/^## (.*?)$/gm, '<h3>$1</h3>');
  content = content.replace(/^# (.*?)$/gm, '<h2>$1</h2>');
  
  // Convert markdown lists to HTML
  const listItemRegex = /^[\*\-] (.*?)$/gm;
  const numberedListItemRegex = /^\d+\. (.*?)$/gm;
  let matches;
  let listItems = [];
  while ((matches = listItemRegex.exec(content)) !== null) {
    listItems.push({
      start: matches.index,
      end: matches.index + matches[0].length,
      html: `<li>${matches[1]}</li>`
    });
  }
  while ((matches = numberedListItemRegex.exec(content)) !== null) {
    listItems.push({
      start: matches.index,
      end: matches.index + matches[0].length,
      html: `<li>${matches[1]}</li>`
    });
  }
  for (let i = listItems.length - 1; i >= 0; i--) {
    const item = listItems[i];
    content = content.substring(0, item.start) + item.html + content.substring(item.end);
  }
  content = content.replace(/(<li>.*?<\/li>\n*)+/gs, function(match) {
    return '<ul>' + match.trim() + '</ul>';
  });
  
  // Convert markdown emphasis
  content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  content = content.replace(/\*(.*?)\*/g, '<em>$1</em>');
  
  // Format blockquotes
  content = content.replace(/^> (.*?)$/gm, '<blockquote>$1</blockquote>');
  
  // Special formatting for summary (key points, citations)
  if (isSummary) {
    content = content.replace(/^(Key (Points|Findings|Takeaways):?)$/gmi, '<h3>$1</h3>');
    content = content.replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>');
  }
  
  // Parse paragraphs respecting double line breaks
  content = content.split(/\n{2,}/).map(para => {
    if (para.trim() && 
        !para.trim().startsWith('<h') && 
        !para.trim().startsWith('<ul') && 
        !para.trim().startsWith('<blockquote') && 
        !para.trim().startsWith('<div class="fact-check"'))
    {
      return `<p>${para.trim()}</p>`;
    }
    return para.trim();
  }).join('\n\n');
  
  // Clean up nested tags
  content = content
    .replace(/<p><ul>/g, '<ul>')
    .replace(/<\/ul><\/p>/g, '</ul>')
    .replace(/<p><h3>/g, '<h3>')
    .replace(/<\/h3><\/p>/g, '</h3>')
    .replace(/<p><h2>/g, '<h2>')
    .replace(/<\/h2><\/p>/g, '</h2>')
    .replace(/<p><blockquote>/g, '<blockquote>')
    .replace(/<\/blockquote><\/p>/g, '</blockquote>')
    .replace(/<p><div class="fact-check">/g, '<div class="fact-check">')
    .replace(/<\/div><\/p>/g, '</div>');
  
  return content;
}
