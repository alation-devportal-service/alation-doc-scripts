function onOpen() {
    var ui = DocumentApp.getUi();
    ui.createMenu('Convert to .RST')
        .addItem('Convert to .RST and email me the result', 'ConvertToRestructuredText')
        .addToUi();
  }
  
  // Adopted from https://github.com/mangini/gdocs2md by Renato Mangini
  // License: Apache License Version 2.0
  String.prototype.repeat = String.prototype.repeat || function(num) {
    var s = '';
    for (var i = 0; i < num; i++) {
      s += this;
    }
    return s;
  };
  
  function ConvertToRestructuredText() {
    var doc = DocumentApp.getActiveDocument();
    var numChildren = doc.getActiveSection().getNumChildren();
    var text = "";
    var inSrc = false;
    var inClass = false;
    var globalImageCounter = 0;
    var globalListCounters = {};
    // edbacher: added a variable for indent in src <pre> block. Let style sheet do margin.
    var srcIndent = "";
    
    var attachments = [];
    
    // Walk through all the child elements of the doc.
    for (var i = 0; i < numChildren; i++) {
      var child = doc.getActiveSection().getChild(i);
      var result = processParagraph(i, child, inSrc, globalImageCounter, globalListCounters);
      globalImageCounter += (result && result.images) ? result.images.length : 0;
      if (result!==null) {
        if (result.sourcePretty==="start" && !inSrc) {
          inSrc=true;
          text+="<pre class=\"prettyprint\">\n";
        } else if (result.sourcePretty==="end" && inSrc) {
          inSrc=false;
          text+="</pre>\n\n";
        } else if (result.source==="start" && !inSrc) {
          inSrc=true;
          text+="<pre>\n";
        } else if (result.source==="end" && inSrc) {
          inSrc=false;
          text+="</pre>\n\n";
        } else if (result.inClass==="start" && !inClass) {
          inClass=true;
          text+="<div class=\""+result.className+"\">\n";
        } else if (result.inClass==="end" && inClass) {
          inClass=false;
          text+="</div>\n\n";
        } else if (inClass) {
          text+=result.text+"\n\n";
        } else if (inSrc) {
          text+=(srcIndent+escapeHTML(result.text)+"\n");
        } else if (result.text && result.text.length>0) {
          text+=result.text+"\n\n";
        }
        
        if (result.images && result.images.length>0) {
          for (var j=0; j<result.images.length; j++) {
            attachments.push( {
              "fileName": result.images[j].name,
              "mimeType": result.images[j].type,
              "content": result.images[j].bytes } );
          }
        }
      } else if (inSrc) { // support empty lines inside source code
        text+='\n';
      }
        
    }
    
    attachments.push({"fileName":doc.getName()+".rst", "mimeType": "text/plain", "content": text});
    
    MailApp.sendEmail(Session.getActiveUser().getEmail(), 
                      "[RST_MAKER] "+doc.getName(), 
                      "Your converted reST document is attached (converted from "+doc.getUrl()+")",
                      { "attachments": attachments });
  }
  
  function escapeHTML(text) {
    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  
  // Process each child element (not just paragraphs).
 function processParagraph(index, element, inSrc, imageCounter, listCounters) {
    if (element.getNumChildren() == 0) {
        return null;
    }

    if (element.getType() === DocumentApp.ElementType.TABLE_OF_CONTENTS) {
        return { "text": "[[TOC]]" };
    }

    var result = {};
    var pOut = "";
    var textElements = [];
    var imagePrefix = "image_";

    // Handle table elements
    if (element.getType() === DocumentApp.ElementType.TABLE) {
        var nCols = element.getChild(0).getNumCells();
        var columnWidths = [];
        var rowHeights = [];

        // Add tabularcolumns directive
        textElements.push('.. tabularcolumns:: |\X{2}{4}|\X{1}{4}|\X{1}{4}|\n\n');

        // Calculate the maximum width and height for each column based on the text length
        for (var j = 0; j < nCols; j++) {
            var maxWidth = 0;
            for (var i = 0; i < element.getNumChildren(); i++) {
                var text = element.getChild(i).getChild(j).getText();
                var lines = text.split('\n');
                for (var k = 0; k < lines.length; k++) {
                    maxWidth = Math.max(maxWidth, lines[k].length);
                }
                rowHeights[i] = Math.max(rowHeights[i] || 0, lines.length);
            }
            columnWidths.push(maxWidth);
        }

        // Construct the table header
        var headerRow = "+" + columnWidths.map(width => "=".repeat(width + 2)).join("+") + "+\n";
        var headerCells = columnWidths.map((width, index) => " " + element.getChild(0).getChild(index).getText() + " ".repeat(width - element.getChild(0).getChild(index).getText().length) + " ").join("|");
        textElements.push(headerRow);
        textElements.push("|" + headerCells + "|\n");
        textElements.push(headerRow);

        // Construct other rows
        for (var i = 1; i < element.getNumChildren(); i++) {
            for (var line = 0; line < rowHeights[i]; line++) {
                textElements.push("|");
                for (var j = 0; j < nCols; j++) {
                    var text = element.getChild(i).getChild(j).getText();
                    var lines = text.split('\n');
                    if (line < lines.length) {
                        var padding = " ".repeat(columnWidths[j] - lines[line].length);
                        textElements.push(" " + lines[line] + padding + " |");
                    } else {
                        textElements.push(" " + " ".repeat(columnWidths[j]) + " |");
                    }
                }
                textElements.push("\n");
            }
            textElements.push("+" + columnWidths.map(width => "-".repeat(width + 2)).join("+") + "+\n");
        }
    }  
    
    
    // Process various types (ElementType).
    for (var i = 0; i < element.getNumChildren(); i++) {
      var t=element.getChild(i).getType();
      
      if (t === DocumentApp.ElementType.TABLE_ROW) {
        // do nothing: already handled TABLE_ROW
      } else if (t === DocumentApp.ElementType.TEXT) {
        var txt=element.getChild(i);
        pOut += txt.getText();
        textElements.push(txt);
      } else if (t === DocumentApp.ElementType.INLINE_IMAGE) {
        result.images = result.images || [];
        var contentType = element.getChild(i).getBlob().getContentType();
        var extension = "";
        if (/\/png$/.test(contentType)) {
          extension = ".png";
        } else if (/\/gif$/.test(contentType)) {
          extension = ".gif";
        } else if (/\/jpe?g$/.test(contentType)) {
          extension = ".jpg";
        } else {
          throw "Unsupported image type: "+contentType;
        }
        var name = imagePrefix + imageCounter + extension;
        imageCounter++;
        textElements.push('.. image:: '+name + '\n');
        result.images.push( {
          "bytes": element.getChild(i).getBlob().getBytes(), 
          "type": contentType, 
          "name": name});
      } else if (t === DocumentApp.ElementType.PAGE_BREAK) {
        // ignore
      } else if (t === DocumentApp.ElementType.HORIZONTAL_RULE) {
        textElements.push('------------\n');
      } else if (t === DocumentApp.ElementType.FOOTNOTE) {
        textElements.push(' (NOTE: '+element.getChild(i).getFootnoteContents().getText()+')');
      } else {
        throw "Paragraph "+index+" of type "+element.getType()+" has an unsupported child: "
        +t+" "+(element.getChild(i)["getText"] ? element.getChild(i).getText():'')+" index="+index;
      }
    }
  
    if (textElements.length==0) {
      // Isn't result empty now?
      return result;
    }
    
    // evb: Add source pretty too. (And abbreviations: src and srcp.)
    // process source code block:
    if (/^\s*---\s+srcp\s*$/.test(pOut) || /^\s*---\s+source pretty\s*$/.test(pOut)) {
      result.sourcePretty = "start";
    } else if (/^\s*---\s+src\s*$/.test(pOut) || /^\s*---\s+source code\s*$/.test(pOut)) {
      result.source = "start";
    } else if (/^\s*---\s+class\s+([^ ]+)\s*$/.test(pOut)) {
      result.inClass = "start";
      result.className = RegExp.$1;
    } else if (/^\s*---\s*$/.test(pOut)) {
      result.source = "end";
      result.sourcePretty = "end";
      result.inClass = "end";
    } else if (/^\s*---\s+jsperf\s*([^ ]+)\s*$/.test(pOut)) {
      result.text = '<iframe style="width: 100%; height: 340px; overflow: hidden; border: 0;" '+
                    'src="http://www.html5rocks.com/static/jsperfview/embed.html?id='+RegExp.$1+
                    '"></iframe>';
    } else {
  
      adornments = findAdornments(inSrc, element, listCounters);
    
      var pOut = "";
      for (var i=0; i<textElements.length; i++) {
        pOut += processTextElement(inSrc, textElements[i]);
      }
  
      // replace Unicode quotation marks
      pOut = pOut.replace('\u201d', '"').replace('\u201c', '"');
   
      result.text = adornments.overline + adornments.prefix + pOut + adornments.underline;
    }
    
    return result;
  }
  
  // Figure out adornments for headings and list items
  function findAdornments(inSrc, element, listCounters) {
    var prefix = "";
    var overline = "";
    var underline = "";
    if (!inSrc) {
      if (element.getType()===DocumentApp.ElementType.PARAGRAPH) {
        var paragraphObj = element;
        var length = paragraphObj.getText().length;
        switch (paragraphObj.getHeading()) {
          // Add a # for each heading level. No break, so we accumulate the right number.
          case DocumentApp.ParagraphHeading.HEADING4:
            underline = "'".repeat(length + 8);
            break;
          case DocumentApp.ParagraphHeading.HEADING3:
            underline = '^'.repeat(length + 8);
            break;
          case DocumentApp.ParagraphHeading.HEADING2:
            underline = '~'.repeat(length + 8);
            break;
          case DocumentApp.ParagraphHeading.HEADING1:
            underline = '-'.repeat(length + 8);
            break;
          case DocumentApp.ParagraphHeading.TITLE:
            overline = '='.repeat(length + 2);
            prefix = ' ';
            underline = '='.repeat(length + 2);
            break;
        }
      } else if (element.getType()===DocumentApp.ElementType.LIST_ITEM) {
        var listItem = element;
        var nesting = listItem.getNestingLevel()
        for (var i=0; i<nesting; i++) {
          prefix += "    ";
        }
        var gt = listItem.getGlyphType();
        // Bullet list (<ul>):
        if (gt === DocumentApp.GlyphType.BULLET
            || gt === DocumentApp.GlyphType.HOLLOW_BULLET
            || gt === DocumentApp.GlyphType.SQUARE_BULLET) {
          prefix += "* ";
        } else {
          // Ordered list (<ol>):
          var key = listItem.getListId() + '.' + listItem.getNestingLevel();
          var counter = listCounters[key] || 0;
          counter++;
          listCounters[key] = counter;
          prefix += counter+". ";
        }
      }
    }
    if (overline) {
      overline += '\n';
    }
    if (underline) {
      underline = '\n' + underline;
    }
    return {
      overline: overline,
      prefix: prefix,
      underline: underline
    };
  }
  
  function processTextElement(inSrc, txt) {
    if (typeof(txt) === 'string') {
      return txt;
    }
    
    var pOut = txt.getText();
    if (! txt.getTextAttributeIndices) {
      return pOut;
    }
    
    var attrs=txt.getTextAttributeIndices();
    var lastOff=pOut.length;
  
    for (var i=attrs.length-1; i>=0; i--) {
      var off=attrs[i];
      var url=txt.getLinkUrl(off);
      var font=txt.getFontFamily(off);
      if (url) {  // start of link
        if (i>=1 && attrs[i-1]==off-1 && txt.getLinkUrl(attrs[i-1])===url) {
          // detect links that are in multiple pieces because of errors on formatting:
          i-=1;
          off=attrs[i];
          url=txt.getLinkUrl(off);
        }
        // Double underscores gives us an "anonymous" link reference, avoids errors for duplicate link text
        pOut=pOut.substring(0, off)+'`'+pOut.substring(off, lastOff)+' <'+url+'>`__'+pOut.substring(lastOff);
      } else if (font) {
        if (!inSrc && font===font.COURIER_NEW) {
          while (i>=1 && txt.getFontFamily(attrs[i-1]) && txt.getFontFamily(attrs[i-1])===font.COURIER_NEW) {
            // detect fonts that are in multiple pieces because of errors on formatting:
            i-=1;
            off=attrs[i];
          }
          pOut=pOut.substring(0, off)+'`'+pOut.substring(off, lastOff)+'`'+pOut.substring(lastOff);
        }
      }
      if (txt.isBold(off)) {
        var d1 = d2 = "**";
        if (txt.isItalic(off)) {
          // edbacher: changed this to handle bold italic properly.
          d1 = "**_"; d2 = "_**";
        }
        pOut=pOut.substring(0, off)+d1+pOut.substring(off, lastOff)+d2+pOut.substring(lastOff);
      } else if (txt.isItalic(off)) {
        pOut=pOut.substring(0, off)+'*'+pOut.substring(off, lastOff)+'*'+pOut.substring(lastOff);
      }
      lastOff=off;
    }
    return pOut;
  }
