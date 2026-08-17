const fs = require("fs");
const path = require("path");
const { Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow, TableCell, BorderStyle, WidthType, convertInchesToTwip } = require("docx");

const FONT = "Times New Roman";

function h1(text) {
  return new Paragraph({
    text: text,
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: true,
  });
}

function h1NoBreak(text) {
  return new Paragraph({
    text: text,
    heading: HeadingLevel.HEADING_1,
  });
}

function h2(text) {
  return new Paragraph({
    text: text,
    heading: HeadingLevel.HEADING_2,
  });
}

function h3(text) {
  return new Paragraph({
    text: text,
    heading: HeadingLevel.HEADING_3,
  });
}

function bodyPar(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text: text, font: FONT, size: 24 })],
  });
}

function labeledPar(label, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    children: [
      new TextRun({ text: label + ": ", bold: true, font: FONT, size: 24 }),
      new TextRun({ text: text, font: FONT, size: 24 }),
    ],
  });
}

function figureCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 300 },
    children: [
      new TextRun({ text: "Figure ", bold: true, font: FONT, size: 20 }),
      new TextRun({ text: text, font: FONT, size: 20 }),
    ],
  });
}

function tableCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 300, after: 100 },
    children: [
      new TextRun({ text: "Table ", bold: true, font: FONT, size: 20 }),
      new TextRun({ text: text, font: FONT, size: 20 }),
    ],
  });
}

function imageParagraph(imgName, widthInches, heightInches) {
  let imgPath;
  if (imgName === "fig1") imgPath = "Figure1.png";
  if (imgName === "fig2") imgPath = "Figure2.png";
  if (imgName === "fig3") imgPath = "Figure3.png";
  
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new ImageRun({
        data: fs.readFileSync(path.join(__dirname, imgPath)),
        transformation: {
          width: widthInches * 96,
          height: heightInches * 96,
        },
      }),
    ],
  });
}

function buildTable(headers, widths, rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1 },
      bottom: { style: BorderStyle.SINGLE, size: 1 },
      left: { style: BorderStyle.SINGLE, size: 1 },
      right: { style: BorderStyle.SINGLE, size: 1 },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 1 },
      insideVertical: { style: BorderStyle.SINGLE, size: 1 },
    },
    rows: [
      new TableRow({
        children: headers.map((h, i) => new TableCell({
          width: { size: widths[i], type: WidthType.DXA },
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: h, bold: true, font: FONT, size: 24 })]
          })],
        })),
      }),
      ...rows.map(row => new TableRow({
        children: row.map((cellText, i) => new TableCell({
          width: { size: widths[i], type: WidthType.DXA },
          children: [new Paragraph({
            alignment: AlignmentType.LEFT,
            children: [new TextRun({ text: cellText, font: FONT, size: 22 })]
          })],
        })),
      })),
    ],
  });
}

module.exports = { FONT, bodyPar, labeledPar, h1, h1NoBreak, h2, h3, figureCaption, tableCaption, imageParagraph, buildTable };
