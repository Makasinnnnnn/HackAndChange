const demoIntro = 'Это авторский демонстрационный материал, а не публикация Альфа-Курса.';

export function MaterialCopy({content, description}: {content: string; description: string}) {
  const paragraphs = content.split(/\n\s*\n/).filter(text => {
    const paragraph = text.trim();
    return paragraph && paragraph !== demoIntro && paragraph !== description.trim();
  });

  return <div className="material-copy">
    {paragraphs.map((paragraph, index) => {
      const lines = paragraph.trim().split('\n');
      const numbered = lines.length > 1 && lines.every((line, i) => line.startsWith(`${i + 1}. `));
      return numbered
        ? <ol key={index}>{lines.map((line, i) => <li key={i}>{line.replace(/^\d+\. /, '')}</li>)}</ol>
        : <p key={index}>{paragraph}</p>;
    })}
  </div>;
}
